from django.conf import settings
from django.db import models

from apps.common.encryption import decrypt_secret, encrypt_secret
from apps.common.models import UUIDTimeStampedModel


class UserPreferences(UUIDTimeStampedModel):
    """Per-user choices that shape how the agent works."""

    class AccountMode(models.TextChoices):
        TEMPORARY = "temporary", "Temporary accounts"
        PERMANENT = "permanent", "Permanent accounts"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences")
    account_mode = models.CharField(max_length=20, choices=AccountMode.choices, default=AccountMode.TEMPORARY)

    @classmethod
    def for_user(cls, user) -> "UserPreferences":
        prefs, _ = cls.objects.get_or_create(user=user)
        return prefs


class ProfileEntry(UUIDTimeStampedModel):
    """
    One saved detail about the user (phone, county, ...), used when the agent
    fills a form for them. Values are encrypted at rest. `source` records
    whether the user typed it in Settings or the agent learned it from an answer.
    """

    class Source(models.TextChoices):
        SETTINGS = "settings", "Settings"
        ANSWER = "answer", "Answered to the agent"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_entries")
    key = models.CharField(max_length=60)
    label = models.CharField(max_length=150)
    encrypted_value = models.TextField()
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.SETTINGS)

    class Meta(UUIDTimeStampedModel.Meta):
        ordering = ["label"]
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="unique_profile_key_per_user")]

    def set_value(self, plaintext: str) -> None:
        self.encrypted_value = encrypt_secret(plaintext)

    def get_value(self) -> str:
        return decrypt_secret(self.encrypted_value)

    @classmethod
    def save_value(cls, user, key: str, value: str, label: str = "", source: str = "settings") -> "ProfileEntry":
        from apps.profiles.standard_fields import LABELS

        entry = cls.objects.filter(user=user, key=key).first() or cls(user=user, key=key)
        entry.label = (label or LABELS.get(key) or key.replace("_", " ").capitalize())[:150]
        entry.source = source
        entry.set_value(value)
        entry.save()
        return entry


class EmailConnection(UUIDTimeStampedModel):
    """
    The user's own mailbox, connected so the agent can read verification codes
    and links for permanent accounts. Either IMAP (app password) or Gmail OAuth.
    The secret (app password or refresh token) is encrypted at rest.
    """

    class Kind(models.TextChoices):
        IMAP = "imap", "IMAP"
        GMAIL = "gmail", "Gmail (Google sign-in)"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_connection")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    address = models.EmailField()
    imap_host = models.CharField(max_length=255, blank=True)
    imap_port = models.PositiveIntegerField(default=993)
    encrypted_secret = models.TextField()
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)

    def set_secret(self, plaintext: str) -> None:
        self.encrypted_secret = encrypt_secret(plaintext)

    def get_secret(self) -> str:
        return decrypt_secret(self.encrypted_secret)

    def __str__(self):
        return f"{self.address} ({self.kind})"
