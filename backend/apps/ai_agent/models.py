from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.registration.models import RegistrationJob


class AgentSession(UUIDTimeStampedModel):
    """Tracks AI provider usage (steps/tokens/cost) for one RegistrationJob."""

    job = models.OneToOneField(
        RegistrationJob, on_delete=models.CASCADE, related_name="agent_session"
    )
    provider = models.CharField(max_length=50)
    model = models.CharField(max_length=100)
    total_steps = models.PositiveIntegerField(default=0)
    total_input_tokens = models.PositiveIntegerField(null=True, blank=True)
    total_output_tokens = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    def __str__(self):
        return f"AgentSession({self.job_id}, {self.provider}/{self.model})"


class SitePlaybook(UUIDTimeStampedModel):
    """
    The steps that worked last time on a site, saved so the next run can replay them without
    asking the AI to work everything out again.

    Contains NO personal data: each typed value is stored as a *source* ("email", "password",
    "first_name", "profile:phone", ...) that is filled in from the current job's own identity
    at replay time. Elements are found again by label, never by the throw-away ids the page
    scan hands out.
    """

    domain = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, default="registration")
    steps = models.JSONField(default=list)
    # What the original job learned about the site's sign-in options (MCP jobs require it).
    auth_check = models.JSONField(default=dict, blank=True)
    success_count = models.PositiveIntegerField(default=0)
    fail_count = models.PositiveIntegerField(default=0)
    # Switched off automatically after repeated failures (the site changed), or by an admin.
    disabled = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        constraints = [models.UniqueConstraint(fields=["domain", "kind"], name="unique_playbook_per_site")]

    def __str__(self):
        return f"Playbook({self.domain}, {len(self.steps)} steps)"
