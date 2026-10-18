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


class ConnectedAccount(UUIDTimeStampedModel):
    """
    A dedicated Google or Microsoft account the user hands to the agent so it can
    submit forms that require a sign-in. One per user and provider.

    Two secrets, both encrypted at rest and never sent to the AI model:
    - the password (optional): lets the agent sign in again when the session expires;
    - the browser session (cookies), saved after a successful sign-in and loaded
      only into that user's own browser, so later jobs usually skip the login.
    """

    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        MICROSOFT = "microsoft", "Microsoft"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="connected_accounts")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    email = models.EmailField()
    encrypted_password = models.TextField(blank=True)
    encrypted_session = models.TextField(blank=True)
    session_saved_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        constraints = [models.UniqueConstraint(fields=["user", "provider"], name="unique_connected_account_per_provider")]

    @property
    def has_password(self) -> bool:
        return bool(self.encrypted_password)

    @property
    def has_session(self) -> bool:
        return bool(self.encrypted_session)

    def set_password(self, plaintext: str) -> None:
        self.encrypted_password = encrypt_secret(plaintext) if plaintext else ""

    def get_password(self) -> str:
        return decrypt_secret(self.encrypted_password) if self.encrypted_password else ""

    def set_session(self, state: dict | None) -> None:
        import json

        from django.utils import timezone

        self.encrypted_session = encrypt_secret(json.dumps(state)) if state else ""
        self.session_saved_at = timezone.now() if state else None

    def get_session(self) -> dict | None:
        import json

        if not self.encrypted_session:
            return None
        try:
            return json.loads(decrypt_secret(self.encrypted_session))
        except Exception:  # noqa: BLE001 - a corrupt/rotated-key session is just "not signed in"
            return None

    def __str__(self):
        return f"{self.email} ({self.provider})"
