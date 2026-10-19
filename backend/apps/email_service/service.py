"""
Email service layer.

Wraps an EmailProvider (chosen via settings.EMAIL_PROVIDER) and adds
persistence: provisioning a mailbox creates/updates a TemporaryEmail
row, and fetching messages upserts EmailMessage rows with extracted
verification link/OTP already filled in. This is the exact code path
Phase 7's `email.*` AI tools will call.
"""
from django.conf import settings
from django.utils import timezone

from apps.common.encryption import encrypt_secret
from apps.email_service.models import EmailMessage, TemporaryEmail
from apps.email_service.providers.base import EmailProvider
from apps.email_service.providers.mailtm import MailTmProvider
from apps.email_service.providers.user_gmail import GmailUserMailboxProvider
from apps.email_service.providers.user_imap import ImapUserMailboxProvider
from apps.identities.models import TemporaryIdentity

_PROVIDERS: dict[str, type[EmailProvider]] = {
    "mailtm": MailTmProvider,
    # The user's own inbox (permanent accounts).
    "imap": ImapUserMailboxProvider,
    "gmail": GmailUserMailboxProvider,
}


class UnknownEmailProviderError(Exception):
    pass


def get_provider(name: str | None = None) -> EmailProvider:
    name = name or settings.EMAIL_PROVIDER
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise UnknownEmailProviderError(
            f"Unknown EMAIL_PROVIDER {name!r}. Registered providers: {list(_PROVIDERS)}"
        )
    return provider_cls()


def create_mailbox_for_identity(identity: TemporaryIdentity) -> TemporaryEmail:
    """
    Provision a real mailbox for `identity` via the configured provider,
    persist it, and back-fill identity.email to match.
    """
    provider = get_provider()
    provisioned = provider.create_mailbox()

    mailbox = TemporaryEmail(
        identity=identity,
        provider=provider.name,
        address=provisioned.address,
        expires_at=identity.expires_at,
    )
    mailbox.set_credential(provisioned.credential)
    mailbox.save()

    identity.email = provisioned.address
    identity.save(update_fields=["email", "updated_at"])

    return mailbox


def attach_user_mailbox(identity: TemporaryIdentity, connection) -> TemporaryEmail:
    """
    Point `identity` at the user's own connected inbox. Only mail arriving from
    now on is visible to the agent (a baseline is recorded here).
    """
    import json
    import time

    from apps.email_service.providers.user_imap import current_uid_baseline, open_imap

    if connection.kind == "imap":
        imap = open_imap(connection.imap_host, connection.imap_port, connection.address, connection.get_secret())
        try:
            baseline = {"baseline_uid": current_uid_baseline(imap)}
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass
    else:
        baseline = {"baseline_ts": int(time.time()) - 5}

    mailbox = TemporaryEmail(
        identity=identity, provider=connection.kind, address=connection.address,
        expires_at=identity.expires_at,
    )
    mailbox.set_credential(json.dumps({"connection_id": str(connection.id), **baseline}))
    mailbox.save()
    identity.email = connection.address
    identity.save(update_fields=["email", "updated_at"])
    return mailbox


def _message_fields(detail, link, otp) -> dict:
    """Column values for an EmailMessage, clipped to the column sizes so one odd message can
    never make the whole mailbox sync fail with "value too long for type character varying"."""
    return {
        "sender": (detail.sender or "")[:255],
        "subject": (detail.subject or "")[:500],
        "text_body": detail.text_body or "",
        "html_body": detail.html_body or "",
        "received_at": detail.received_at or timezone.now(),
        "extracted_link": (link or "")[:2000],
        "extracted_otp": (otp or "")[:20],
    }


def sync_messages(mailbox: TemporaryEmail) -> list[EmailMessage]:
    """Fetch the mailbox's current message list and upsert them locally."""
    provider = get_provider(mailbox.provider)
    credential = mailbox.get_credential()
    summaries = provider.get_messages(credential)

    saved = []
    for summary in summaries:
        detail = provider.get_message(credential, summary.external_id)
        link = provider.extract_verification_link(detail)
        otp = provider.extract_otp(detail)

        message, _created = EmailMessage.objects.update_or_create(
            mailbox=mailbox,
            external_id=(detail.external_id or "")[:255],
            defaults=_message_fields(detail, link, otp),
        )
        saved.append(message)
    return saved


def wait_for_verification_email(
    mailbox: TemporaryEmail, timeout_seconds: int = 60
) -> EmailMessage | None:
    """
    Block (via provider polling) until a message arrives, persist it, and
    return the saved EmailMessage — or None if nothing arrived in time.
    """
    provider = get_provider(mailbox.provider)
    credential = mailbox.get_credential()
    detail = provider.wait_for_message(credential, timeout_seconds=timeout_seconds)
    if detail is None:
        return None

    link = provider.extract_verification_link(detail)
    otp = provider.extract_otp(detail)

    message, _created = EmailMessage.objects.update_or_create(
        mailbox=mailbox,
        external_id=(detail.external_id or "")[:255],
        defaults=_message_fields(detail, link, otp),
    )
    return message
