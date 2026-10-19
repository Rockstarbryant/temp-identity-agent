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


def _store(mailbox: TemporaryEmail, provider: EmailProvider, detail) -> tuple[EmailMessage, bool]:
    """Save one fetched message; announce it to the user the first time it is seen."""
    link = provider.extract_verification_link(detail)
    otp = provider.extract_otp(detail)
    message, created = EmailMessage.objects.update_or_create(
        mailbox=mailbox,
        external_id=(detail.external_id or "")[:255],
        defaults=_message_fields(detail, link, otp),
    )
    if created:
        _announce_new_mail(mailbox, message)
    return message, created


def _sender_name(sender: str) -> str:
    name = (sender or "").split("<")[0].strip().strip('"')
    if name:
        return name
    return (sender or "").split("@")[-1].strip(" >") or "an unknown sender"


def _announce_new_mail(mailbox: TemporaryEmail, message: EmailMessage) -> None:
    from apps.accounts.models import TemporaryAccount
    from apps.notifications.models import Notification
    from apps.notifications.service import notify

    try:
        identity = mailbox.identity
        account = identity.accounts.exclude(status=TemporaryAccount.Status.DELETED).first()
        job = identity.jobs.order_by("-created_at").first()
        if account is not None:
            link = f"/accounts/{account.id}"
            domain = account.website.domain
        elif job is not None:
            link, domain = f"/jobs/{job.id}", job.target_website.domain
        else:
            link, domain = "/accounts", ""
        extras = []
        if message.extracted_link:
            extras.append("has a link")
        if message.extracted_otp:
            extras.append(f"code {message.extracted_otp}")
        body = message.subject or "(no subject)"
        if extras:
            body += " — " + ", ".join(extras)
        notify(
            identity.user, Notification.Kind.MAIL_RECEIVED, f"New email from {_sender_name(message.sender)}", body,
            link,
            {"message_id": str(message.id), "account_id": str(account.id) if account else "", "domain": domain,
             "has_link": bool(message.extracted_link), "has_code": bool(message.extracted_otp)},
            f"mail:{message.id}",
        )
    except Exception:  # noqa: BLE001 - a notification problem must never break a mailbox sync
        import logging

        logging.getLogger("apps.email_service").exception("Could not announce mail %s", message.id)


def _sync(mailbox: TemporaryEmail) -> tuple[list[EmailMessage], list[EmailMessage]]:
    """Fetch the mailbox's message list. Only messages not seen before are downloaded in full."""
    provider = get_provider(mailbox.provider)
    credential = mailbox.get_credential()
    summaries = provider.get_messages(credential)
    known = {m.external_id: m for m in EmailMessage.objects.filter(mailbox=mailbox)}

    everything: list[EmailMessage] = []
    created_now: list[EmailMessage] = []
    for summary in summaries:
        existing = known.get((summary.external_id or "")[:255])
        if existing is not None:
            everything.append(existing)
            continue
        detail = provider.get_message(credential, summary.external_id)
        message, created = _store(mailbox, provider, detail)
        everything.append(message)
        if created:
            created_now.append(message)
    TemporaryEmail.objects.filter(pk=mailbox.pk).update(last_polled_at=timezone.now())
    return everything, created_now


def sync_messages(mailbox: TemporaryEmail) -> list[EmailMessage]:
    """Fetch the mailbox's current message list and save new messages locally."""
    return _sync(mailbox)[0]


def sync_new_messages(mailbox: TemporaryEmail) -> list[EmailMessage]:
    """Like sync_messages, but returns only the messages that had not been seen before."""
    return _sync(mailbox)[1]


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
    message, _created = _store(mailbox, provider, detail)
    return message


def mailbox_is_pollable(mailbox: TemporaryEmail) -> bool:
    return (
        mailbox.status == TemporaryEmail.Status.ACTIVE
        and bool(mailbox.encrypted_credential)
        and mailbox.expires_at > timezone.now()
    )


def poll_mailbox(mailbox: TemporaryEmail) -> int:
    """Check one mailbox for new mail. Returns how many new messages arrived; never raises."""
    import logging

    if not mailbox_is_pollable(mailbox):
        return 0
    try:
        return len(sync_new_messages(mailbox))
    except Exception:  # noqa: BLE001 - one provider outage must not stop the others
        logging.getLogger("apps.email_service").warning("Polling mailbox %s failed", mailbox.id, exc_info=True)
        TemporaryEmail.objects.filter(pk=mailbox.pk).update(last_polled_at=timezone.now())
        return 0


def poll_user_mailboxes(user, min_age_seconds: int = 25, limit: int = 10) -> int:
    """Poll this user's live mailboxes that have not been checked recently (used by the live stream)."""
    from datetime import timedelta

    from django.db.models import Q

    cutoff = timezone.now() - timedelta(seconds=min_age_seconds)
    boxes = (
        TemporaryEmail.objects.filter(
            identity__user=user, status=TemporaryEmail.Status.ACTIVE, expires_at__gt=timezone.now()
        )
        .exclude(encrypted_credential="")
        .filter(Q(last_polled_at__isnull=True) | Q(last_polled_at__lt=cutoff))
        .select_related("identity")
        .order_by("last_polled_at")[:limit]
    )
    return sum(poll_mailbox(b) for b in boxes)
