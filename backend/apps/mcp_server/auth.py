from django.utils import timezone
from rest_framework import authentication, exceptions

from apps.mcp_server.models import KEY_PREFIX, ApiKey


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """`Authorization: Bearer tia_...` — resolves to the key's owner."""

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("utf-8", "ignore")
        if not header.lower().startswith("bearer "):
            return None
        raw = header[7:].strip()
        if not raw.startswith(KEY_PREFIX):
            return None  # not ours (e.g. a JWT)
        key = ApiKey.objects.select_related("user").filter(
            key_hash=ApiKey.hash_key(raw), revoked_at__isnull=True
        ).first()
        if key is None or not key.user.is_active:
            raise exceptions.AuthenticationFailed("Invalid or revoked API key.")
        ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return key.user, key

    def authenticate_header(self, request):
        return "Bearer"
