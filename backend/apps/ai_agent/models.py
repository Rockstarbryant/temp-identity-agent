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
