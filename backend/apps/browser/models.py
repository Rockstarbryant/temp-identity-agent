from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.registration.models import RegistrationJob


class BrowserSession(UUIDTimeStampedModel):
    """Tracks one Playwright browser session backing a RegistrationJob."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        CRASHED = "crashed", "Crashed"

    job = models.OneToOneField(
        RegistrationJob, on_delete=models.CASCADE, related_name="browser_session"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    session_metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [models.Index(fields=["job", "status"])]

    def __str__(self):
        return f"BrowserSession({self.job_id}, {self.status})"
