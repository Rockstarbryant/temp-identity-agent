from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "user", "kind", "title", "read_at")
    list_filter = ("kind",)
    search_fields = ("title", "user__username")
