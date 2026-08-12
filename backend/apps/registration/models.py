from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.identities.models import TemporaryIdentity


class TargetWebsite(UUIDTimeStampedModel):
    domain = models.CharField(max_length=255, unique=True)
    registration_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [models.Index(fields=["domain"])]

    def __str__(self):
        return self.domain


class DomainPolicy(UUIDTimeStampedModel):
    """Admin-controlled allow/block list, checked before any job starts."""

    class Status(models.TextChoices):
        ALLOWED = "allowed", "Allowed"
        BLOCKED = "blocked", "Blocked"
        REQUIRES_HUMAN = "requires_human", "Requires human"
        UNSUPPORTED = "unsupported", "Unsupported"

    domain = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ALLOWED)
    reason = models.TextField(blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [models.Index(fields=["domain", "status"])]

    def __str__(self):
        return f"{self.domain}: {self.status}"


class RegistrationJob(UUIDTimeStampedModel):
    """
    The unit of work: one attempt to register a temporary identity on
    a target website. Drives the agent state machine end to end.
    """

    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        STARTING = "starting", "Starting"
        OPENING_SITE = "opening_site", "Opening site"
        ANALYZING = "analyzing", "Analyzing"
        IDENTITY_CREATED = "identity_created", "Identity created"
        FILLING_FORM = "filling_form", "Filling form"
        SUBMITTING = "submitting", "Submitting"
        WAITING_FOR_EMAIL = "waiting_for_email", "Waiting for email"
        VERIFYING = "verifying", "Verifying"
        COMPLETED = "completed", "Completed"
        CAPTCHA_REQUIRED = "captcha_required", "CAPTCHA required"
        HUMAN_ACTION_REQUIRED = "human_action_required", "Human action required"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    # States from which the job may still be resumed by the user
    RESUMABLE_STATES = {State.CAPTCHA_REQUIRED, State.HUMAN_ACTION_REQUIRED}
    # Terminal states — no further transitions allowed
    TERMINAL_STATES = {State.COMPLETED, State.FAILED, State.CANCELLED, State.EXPIRED}
    # States that count against a user's concurrent-job quota
    ACTIVE_STATES = {
        State.QUEUED, State.STARTING, State.OPENING_SITE, State.ANALYZING,
        State.IDENTITY_CREATED, State.FILLING_FORM, State.SUBMITTING,
        State.WAITING_FOR_EMAIL, State.VERIFYING,
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registration_jobs"
    )
    target_website = models.ForeignKey(
        TargetWebsite, on_delete=models.CASCADE, related_name="jobs"
    )
    identity = models.ForeignKey(
        TemporaryIdentity, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs"
    )
    state = models.CharField(max_length=30, choices=State.choices, default=State.QUEUED)
    max_steps = models.PositiveIntegerField(default=30)
    timeout_seconds = models.PositiveIntegerField(default=300)
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [
            models.Index(fields=["user", "state"]),
            models.Index(fields=["state", "created_at"]),
        ]

    def can_transition_to(self, new_state: str) -> bool:
        return self.state not in self.TERMINAL_STATES

    def __str__(self):
        return f"Job {self.id} — {self.target_website.domain} [{self.state}]"


class RegistrationStep(UUIDTimeStampedModel):
    """
    One audit-trail entry per agent action: which tool was called, with
    what arguments, and what came back. This is the full accountability
    log for what the AI agent actually did during a job.
    """

    job = models.ForeignKey(RegistrationJob, on_delete=models.CASCADE, related_name="steps")
    step_index = models.PositiveIntegerField()
    action = models.CharField(max_length=100)
    tool_name = models.CharField(max_length=100, blank=True)
    tool_input = models.JSONField(default=dict, blank=True)
    tool_result = models.JSONField(default=dict, blank=True)
    screenshot_path = models.CharField(max_length=500, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        ordering = ["job", "step_index"]
        constraints = [
            models.UniqueConstraint(fields=["job", "step_index"], name="unique_job_step_index")
        ]
        indexes = [models.Index(fields=["job", "step_index"])]

    def __str__(self):
        return f"Job {self.job_id} step {self.step_index}: {self.action}"
