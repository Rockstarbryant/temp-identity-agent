from django.conf import settings
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


class ChatConversation(UUIDTimeStampedModel):
    """
    One conversation with the agent. Every vault account has one (linked via `account`); others
    start from "New chat" and get linked to the account they create, if any.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_conversations")
    account = models.ForeignKey(TemporaryAccount, null=True, blank=True, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=120, blank=True)

    class Meta(UUIDTimeStampedModel.Meta):
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]
        constraints = [
            models.UniqueConstraint(fields=["account"], condition=models.Q(account__isnull=False),
                                    name="one_conversation_per_account"),
        ]


class AccountChatMessage(UUIDTimeStampedModel):
    """One turn of a conversation."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        TASK_STARTED = "task_started", "Website task started"
        TASK_RESULT = "task_result", "Website task result"

    conversation = models.ForeignKey(ChatConversation, null=True, on_delete=models.CASCADE, related_name="messages")
    account = models.ForeignKey(TemporaryAccount, null=True, blank=True, on_delete=models.CASCADE, related_name="chat_messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.TEXT)
    content = models.TextField()
    # What the assistant did to produce this reply, e.g. [{"name": "mailbox_list", "label": "Checked the mailbox", "ok": true}]
    actions = models.JSONField(default=list, blank=True)
    job = models.ForeignKey(RegistrationJob, null=True, blank=True, on_delete=models.SET_NULL, related_name="chat_messages")

    class Meta(UUIDTimeStampedModel.Meta):
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["job", "kind"], condition=models.Q(kind="task_result"),
                                    name="one_task_result_per_job"),
        ]
