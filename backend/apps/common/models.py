import uuid

from django.db import models


class UUIDTimeStampedModel(models.Model):
    """
    Abstract base for every domain model in this project.

    Gives every table a UUID primary key (so IDs are not guessable /
    enumerable, which matters for a system that stores credentials)
    plus created_at / updated_at timestamps.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
