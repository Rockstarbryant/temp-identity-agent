from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import TemporaryAccount


@admin.register(TemporaryAccount)
class TemporaryAccountAdmin(ReadOnlyAdmin):
    list_display = ("website", "identity", "status", "revealed_at", "created_at")
    list_filter = ("status",)
    search_fields = ("website__domain", "identity__email")
