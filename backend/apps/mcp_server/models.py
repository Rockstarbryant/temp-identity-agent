import hashlib
import secrets

from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel

KEY_PREFIX = "tia_"


class ApiKey(UUIDTimeStampedModel):
    """
    Bearer key for external AI clients using the MCP endpoint. Only a SHA-256
    hash is stored; the full key is shown once, when it is created.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=80)
    prefix = models.CharField(max_length=12)
    key_hash = models.CharField(max_length=64, unique=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    # "manual" keys are created in Settings; "oauth" keys are short-lived access tokens
    # issued when a client such as claude.ai is connected through the OAuth sign-in.
    kind = models.CharField(max_length=10, default="manual")
    expires_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def create_for(cls, user, name: str, kind: str = "manual", expires_at=None) -> tuple["ApiKey", str]:
        raw = KEY_PREFIX + secrets.token_urlsafe(32)
        key = cls.objects.create(
            user=user, name=name[:80], prefix=raw[:10], key_hash=cls.hash_key(raw), kind=kind, expires_at=expires_at
        )
        return key, raw

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class OAuthClient(UUIDTimeStampedModel):
    """An MCP client that registered itself (RFC 7591), e.g. claude.ai. Public client: PKCE, no secret."""

    client_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    redirect_uris = models.JSONField(default=list)

    def __str__(self):
        return self.name


class OAuthCode(UUIDTimeStampedModel):
    """One-time authorization code (10 minutes), bound to the client, redirect URI and PKCE challenge."""

    code_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    redirect_uri = models.TextField()
    code_challenge = models.CharField(max_length=128)
    expires_at = models.DateTimeField()

    @staticmethod
    def hash(code: str) -> str:
        return _sha(code)


class OAuthGrant(UUIDTimeStampedModel):
    """A user's connection to one client. Holds the rotating refresh token and the current access key."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="oauth_grants")
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE)
    refresh_hash = models.CharField(max_length=64, unique=True)
    api_key = models.ForeignKey(ApiKey, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def hash(token: str) -> str:
        return _sha(token)
