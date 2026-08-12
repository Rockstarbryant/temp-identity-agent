from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel


class AuditLog(UUIDTimeStampedModel):
    """
    Append-only record of security-relevant actions: logins, credential
    reveals, job creation/cancellation, admin domain-policy changes, etc.
    Never store passwords/tokens/secrets in `metadata`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [
            models.Index(fields=["user", "action"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.user_id} at {self.created_at}"
