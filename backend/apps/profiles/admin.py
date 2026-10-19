from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import ConnectedAccount, EmailConnection, ProfileEntry, UserPreferences


@admin.register(UserPreferences)
class UserPreferencesAdmin(ReadOnlyAdmin):
    list_display = ("user", "account_mode", "updated_at")


@admin.register(ProfileEntry)
class ProfileEntryAdmin(ReadOnlyAdmin):
    secret_fields = ("encrypted_value",)
    list_display = ("user", "key", "label", "source", "updated_at")
    search_fields = ("user__username", "key", "label")


@admin.register(EmailConnection)
class EmailConnectionAdmin(ReadOnlyAdmin):
    secret_fields = ("encrypted_secret",)
    list_display = ("user", "kind", "address", "last_checked_at", "last_error")


@admin.register(ConnectedAccount)
class ConnectedAccountAdmin(ReadOnlyAdmin):
    secret_fields = ("encrypted_password", "encrypted_session")
    list_display = ("user", "provider", "email", "session_saved_at", "last_used_at", "last_error")
    list_filter = ("provider",)
