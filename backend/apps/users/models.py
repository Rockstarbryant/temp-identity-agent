import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model (UUID pk instead of Django's default integer pk),
    so user IDs exposed in the API are not sequential/enumerable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def __str__(self):
        return self.username
