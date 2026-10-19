from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    """
    One thing the user should know about. The auto-increment id doubles as the SSE event id,
    so a reconnecting browser can ask for "everything after id N" and miss nothing.
    """

    class Kind(models.TextChoices):
        JOB_STARTED = "job_started", "Job started"
        JOB_COMPLETED = "job_completed", "Job completed"
        JOB_FAILED = "job_failed", "Job failed"
        JOB_CANCELLED = "job_cancelled", "Job cancelled"
        JOB_NEEDS_YOU = "job_needs_you", "Needs your help"
        JOB_QUESTION = "job_question", "Agent has a question"
        MAIL_RECEIVED = "mail_received", "New email"
        ACCOUNT_EXPIRING = "account_expiring", "Account expiring soon"
        ACCOUNT_EXPIRED = "account_expired", "Account expired"
        SIGNIN_ISSUE = "signin_issue", "Connected account needs attention"
        CLIENT_CONNECTED = "client_connected", "AI client connected"
        MANUAL_SAVED = "manual_saved", "Manual sign-up saved"
        PLAYBOOK_USED = "playbook_used", "Saved steps used"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    # Frontend path to open when the notification is clicked, e.g. "/jobs/<id>".
    link = models.CharField(max_length=200, blank=True)
    data = models.JSONField(default=dict, blank=True)
    # Stops the same event being announced twice (e.g. "mail:<message id>", "job:<id>:completed").
    dedupe_key = models.CharField(max_length=120, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["user", "-id"]),
            models.Index(fields=["user", "read_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedupe_key"], condition=~Q(dedupe_key=""), name="unique_notification_dedupe"
            )
        ]

    def __str__(self):
        return f"{self.kind}: {self.title}"
