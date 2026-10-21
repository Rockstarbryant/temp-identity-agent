"""When a website task started from chat finishes, put its outcome in the conversation."""
import json
import logging

from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.registration.models import RegistrationJob

logger = logging.getLogger(__name__)
STATES = RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES


def _text(job) -> str:
    S = RegistrationJob.State
    if job.state == S.COMPLETED:
        result = job.result or {}
        parts = [result.get("summary") or "The task finished."]
        data = result.get("data")
        if data:
            try:
                parts.append("\n".join(f"- {k}: {v}" for k, v in dict(data).items())[:2500])
            except (TypeError, ValueError):
                parts.append(json.dumps(data, default=str)[:2500])
        return "\n".join(parts)
    if job.state in (S.CAPTCHA_REQUIRED, S.HUMAN_ACTION_REQUIRED):
        return f"The task needs you: {job.error_message or 'a manual step is needed on the site.'} Open the task to continue it."
    if job.state == S.CANCELLED:
        return "The task was cancelled."
    return f"The task didn't work out: {job.error_message or 'it failed.'}"


@receiver(post_save, sender=RegistrationJob)
def task_finished(sender, instance: RegistrationJob, **kwargs):
    if instance.kind != RegistrationJob.Kind.ACCOUNT_TASK or instance.state not in STATES:
        return
    try:
        from apps.accounts.models import AccountChatMessage, TemporaryAccount

        account = TemporaryAccount.objects.filter(identity_id=instance.identity_id).first()
        if account is None:
            return
        AccountChatMessage.objects.update_or_create(
            job=instance, kind="task_result",
            defaults={"account": account, "role": "assistant", "content": _text(instance)[:4000]},
        )
    except IntegrityError:
        pass
    except Exception:  # noqa: BLE001 - never break saving a job
        logger.exception("Could not post the task result for job %s", instance.id)
