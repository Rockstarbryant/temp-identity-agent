from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.identities.models import TemporaryIdentity
from apps.registration.models import RegistrationJob, TargetWebsite


class TemporaryAccount(UUIDTimeStampedModel):
    """
    The user-facing vault entry: a completed registration, ready to
    have its credentials revealed on demand.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        DELETED = "deleted", "Deleted"

    job = models.OneToOneField(RegistrationJob, on_delete=models.CASCADE, related_name="account")
    identity = models.ForeignKey(TemporaryIdentity, on_delete=models.CASCADE, related_name="accounts")
    website = models.ForeignKey(TargetWebsite, on_delete=models.CASCADE, related_name="accounts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    revealed_at = models.DateTimeField(null=True, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.website.domain} — {self.identity.email}"
