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

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def create_for(cls, user, name: str) -> tuple["ApiKey", str]:
        raw = KEY_PREFIX + secrets.token_urlsafe(32)
        key = cls.objects.create(user=user, name=name[:80], prefix=raw[:10], key_hash=cls.hash_key(raw))
        return key, raw

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"
