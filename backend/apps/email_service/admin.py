from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import EmailMessage, TemporaryEmail


@admin.register(TemporaryEmail)
class TemporaryEmailAdmin(ReadOnlyAdmin):
    secret_fields = ("encrypted_credential",)
    list_display = ("address", "provider", "status", "expires_at", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("address",)


@admin.register(EmailMessage)
class EmailMessageAdmin(ReadOnlyAdmin):
    # Bodies, OTP codes and verification links belong to the user, so they are not shown.
    secret_fields = ("text_body", "html_body", "extracted_otp", "extracted_link")
    list_display = ("subject", "sender", "mailbox", "received_at")
    search_fields = ("subject", "sender")
