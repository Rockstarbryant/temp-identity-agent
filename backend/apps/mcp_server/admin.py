from django.contrib import admin
from django.utils import timezone

from apps.common.admin import ReadOnlyAdmin

from .models import ApiKey, OAuthClient, OAuthCode, OAuthGrant


@admin.register(ApiKey)
class ApiKeyAdmin(ReadOnlyAdmin):
    secret_fields = ("key_hash",)
    list_display = ("name", "prefix", "user", "kind", "last_used_at", "expires_at", "revoked_at")
    list_filter = ("kind",)
    search_fields = ("name", "prefix", "user__username")
    actions = ["revoke_selected"]

    @admin.action(description="Revoke selected keys")
    def revoke_selected(self, request, queryset):
        n = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f"Revoked {n} key(s).")


@admin.register(OAuthClient)
class OAuthClientAdmin(ReadOnlyAdmin):
    list_display = ("name", "client_id", "created_at")
    search_fields = ("name", "client_id")


@admin.register(OAuthCode)
class OAuthCodeAdmin(ReadOnlyAdmin):
    secret_fields = ("code_hash", "code_challenge")
    list_display = ("user", "client", "expires_at", "created_at")


@admin.register(OAuthGrant)
class OAuthGrantAdmin(ReadOnlyAdmin):
    secret_fields = ("refresh_hash",)
    list_display = ("user", "client", "expires_at", "revoked_at", "created_at")
