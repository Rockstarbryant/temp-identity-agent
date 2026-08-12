from django.conf import settings
from django.db import models

from apps.common.encryption import decrypt_secret, encrypt_secret
from apps.common.models import UUIDTimeStampedModel


class TemporaryIdentity(UUIDTimeStampedModel):
    """
    A generated throwaway identity used to register on a target site.

    The password is never stored in plaintext — `set_password()` /
    `get_password()` go through Fernet authenticated encryption
    (apps.common.encryption), keyed by CREDENTIAL_ENCRYPTION_KEY.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="temporary_identities"
    )
    name = models.CharField(max_length=150)
    username = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    encrypted_password = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def set_password(self, plaintext: str) -> None:
        self.encrypted_password = encrypt_secret(plaintext)

    def get_password(self) -> str:
        return decrypt_secret(self.encrypted_password)

    def __str__(self):
        return f"{self.email} ({self.status})"
