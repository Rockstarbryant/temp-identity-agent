from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import TemporaryIdentity


@admin.register(TemporaryIdentity)
class TemporaryIdentityAdmin(ReadOnlyAdmin):
    secret_fields = ("encrypted_password",)
    list_display = ("email", "username", "user", "status", "expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "username", "user__username")
    date_hierarchy = "created_at"
