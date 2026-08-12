from django.db import models

from apps.common.encryption import decrypt_secret, encrypt_secret
from apps.common.models import UUIDTimeStampedModel
from apps.identities.models import TemporaryIdentity


class TemporaryEmail(UUIDTimeStampedModel):
    """
    A disposable mailbox tied to a TemporaryIdentity.

    `encrypted_credential` holds whatever the provider needs to poll the
    mailbox (e.g. mail.tm returns a JWT after account creation) — never
    stored in plaintext.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"

    identity = models.OneToOneField(
        TemporaryIdentity, on_delete=models.CASCADE, related_name="mailbox"
    )
    provider = models.CharField(max_length=50)
    address = models.EmailField()
    encrypted_credential = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [models.Index(fields=["address"])]

    def set_credential(self, plaintext: str) -> None:
        self.encrypted_credential = encrypt_secret(plaintext)

    def get_credential(self) -> str:
        return decrypt_secret(self.encrypted_credential)

    def __str__(self):
        return self.address


class EmailMessage(UUIDTimeStampedModel):
    """A single message fetched from a TemporaryEmail mailbox."""

    mailbox = models.ForeignKey(TemporaryEmail, on_delete=models.CASCADE, related_name="messages")
    external_id = models.CharField(max_length=255, help_text="Provider's message ID")
    sender = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    text_body = models.TextField(blank=True)
    html_body = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    extracted_link = models.URLField(blank=True)
    extracted_otp = models.CharField(max_length=20, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [models.Index(fields=["mailbox", "received_at"])]
        constraints = [
            models.UniqueConstraint(fields=["mailbox", "external_id"], name="unique_mailbox_message")
        ]

    def __str__(self):
        return f"{self.subject} ({self.mailbox.address})"
