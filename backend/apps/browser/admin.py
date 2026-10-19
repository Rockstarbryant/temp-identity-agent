from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import BrowserSession


@admin.register(BrowserSession)
class BrowserSessionAdmin(ReadOnlyAdmin):
    list_display = ("job", "status", "started_at", "ended_at")
    list_filter = ("status",)
