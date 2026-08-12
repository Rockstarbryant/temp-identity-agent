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
from apps.identities.models import TemporaryIdentity

_PROVIDERS: dict[str, type[EmailProvider]] = {
    "mailtm": MailTmProvider,
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
            external_id=detail.external_id,
            defaults={
                "sender": detail.sender,
                "subject": detail.subject,
                "text_body": detail.text_body,
                "html_body": detail.html_body,
                "received_at": detail.received_at or timezone.now(),
                "extracted_link": link or "",
                "extracted_otp": otp or "",
            },
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
        external_id=detail.external_id,
        defaults={
            "sender": detail.sender,
            "subject": detail.subject,
            "text_body": detail.text_body,
            "html_body": detail.html_body,
            "received_at": detail.received_at or timezone.now(),
            "extracted_link": link or "",
            "extracted_otp": otp or "",
        },
    )
    return message
