"""When a task started from chat finishes (or needs the user), put the outcome in the conversation."""
import json
import logging

from django.db import IntegrityError
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.registration.models import RegistrationJob

logger = logging.getLogger(__name__)
STATES = RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES


def _text(job, account) -> str:
    S = RegistrationJob.State
    domain = job.target_website.domain
    if job.state == S.COMPLETED:
        result = job.result or {}
        if job.kind == RegistrationJob.Kind.FORM and result.get("submitted"):
            parts = [f"The form on {domain} was submitted."]
        elif job.kind == RegistrationJob.Kind.REGISTRATION:
            parts = [f"Signed up on {domain}." + (" The account is saved in your vault, and this conversation is now about it." if account else "")]
            if result.get("summary"):
                parts.append(result["summary"])
        else:
            parts = [result.get("summary") or "The task finished."]
        data = result.get("data")
        if data:
            try:
                parts.append("\n".join(f"- {k}: {v}" for k, v in dict(data).items())[:2500])
            except (TypeError, ValueError):
                parts.append(json.dumps(data, default=str)[:2500])
        return "\n".join(parts)
    if job.state in (S.CAPTCHA_REQUIRED, S.HUMAN_ACTION_REQUIRED):
        return f"The task needs you: {job.error_message or 'a manual step is needed on the site.'}"
    if job.state == S.CANCELLED:
        return "The task was cancelled."
    return f"The task didn't work out: {job.error_message or 'it failed.'}"


@receiver(post_save, sender=RegistrationJob)
def task_finished(sender, instance: RegistrationJob, **kwargs):
    if instance.state not in STATES:
        return
    try:
        from apps.accounts.models import AccountChatMessage, TemporaryAccount
        from apps.accounts.service import ensure_vault_account

        started = AccountChatMessage.objects.filter(job=instance, kind="task_started").select_related("conversation").first()
        if started is None or started.conversation is None:
            return
        convo = started.conversation
        account = None
        if instance.state == RegistrationJob.State.COMPLETED:
            if instance.kind == RegistrationJob.Kind.REGISTRATION:
                account = ensure_vault_account(instance)  # the agent creates it a moment later; this is idempotent
            elif instance.identity_id:
                account = TemporaryAccount.objects.filter(identity_id=instance.identity_id).first()
        if account is not None and convo.account_id is None and not account.conversations.exists():
            convo.account = account
            convo.save(update_fields=["account", "updated_at"])
        AccountChatMessage.objects.update_or_create(
            job=instance, kind="task_result",
            defaults={"conversation": convo, "account": convo.account, "role": "assistant", "content": _text(instance, account)[:4000]},
        )
    except IntegrityError:
        pass
    except Exception:  # noqa: BLE001 - never break saving a job
        logger.exception("Could not post the task result for job %s", instance.id)
