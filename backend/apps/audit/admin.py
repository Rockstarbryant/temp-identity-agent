from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "user", "action", "resource_type", "resource_id", "ip_address")
    list_filter = ("action", "resource_type")
    search_fields = ("user__username", "action", "resource_id")
    date_hierarchy = "created_at"

    def has_delete_permission(self, request, obj=None):
        return False  # the audit trail is append-only
