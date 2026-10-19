"""
Turns job state changes into notifications, without touching any of the code that changes
the state. Every place that saves a RegistrationJob (the agent, the views, Celery tasks)
is covered by listening for the model signals.
"""
import logging

from django.db.models.signals import post_init, post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.service import notify
from apps.registration.models import RegistrationJob

logger = logging.getLogger("apps.notifications")
S = RegistrationJob.State
K = Notification.Kind

_STARTED_FROM = {S.QUEUED}


@receiver(post_init, sender=RegistrationJob)
def _remember_state(sender, instance, **kwargs):
    instance._notified_state = instance.state


def _site(job) -> str:
    try:
        return job.target_website.domain
    except Exception:  # noqa: BLE001
        return "the site"


def _verb(job) -> str:
    if job.kind == RegistrationJob.Kind.FORM:
        return "Form"
    if job.kind == RegistrationJob.Kind.ACCOUNT_SETUP:
        return "Account connection"
    return "Sign-up"


@receiver(post_save, sender=RegistrationJob)
def job_state_changed(sender, instance: RegistrationJob, created: bool, **kwargs):
    previous = getattr(instance, "_notified_state", None)
    state = instance.state
    instance._notified_state = state
    if created or previous == state:
        return
    try:
        _announce(instance, previous, state)
    except Exception:  # noqa: BLE001 - never let this break saving the job
        logger.exception("Could not announce job %s state %s", instance.id, state)


def _announce(job: RegistrationJob, previous: str | None, state: str) -> None:
    site = _site(job)
    link = f"/jobs/{job.id}"
    base = {"job_id": str(job.id), "domain": site, "state": state}
    verb = _verb(job)
    key = f"job:{job.id}:"

    if previous in _STARTED_FROM and state not in RegistrationJob.TERMINAL_STATES:
        notify(job.user, K.JOB_STARTED, f"{verb} started on {site}", "The agent picked it up from the queue.",
               link, base, key + "started")

    if state == S.COMPLETED:
        manual = bool((job.result or {}).get("manual"))
        notify(job.user, K.JOB_COMPLETED,
               f"{verb} finished on {site}" if not manual else f"Saved your {site} sign-up",
               "Open it to see the result." if job.kind != RegistrationJob.Kind.REGISTRATION
               else "The account is in your vault.", link, base, key + "completed")
    elif state == S.FAILED:
        notify(job.user, K.JOB_FAILED, f"{verb} failed on {site}", job.error_message[:300] or "Open it for details.",
               link, {**base, "error_code": job.error_code}, key + "failed")
    elif state == S.CANCELLED:
        notify(job.user, K.JOB_CANCELLED, f"{verb} on {site} was cancelled", "", link, base, key + "cancelled")
    elif state == S.EXPIRED:
        notify(job.user, K.JOB_FAILED, f"{verb} on {site} timed out", "It ran too long and was stopped.",
               link, base, key + "expired")
    elif state in (S.CAPTCHA_REQUIRED, S.HUMAN_ACTION_REQUIRED):
        what = "a CAPTCHA" if state == S.CAPTCHA_REQUIRED else "a manual step"
        notify(job.user, K.JOB_NEEDS_YOU, f"{site} needs you", f"The agent hit {what}. Solve it in the live view or sign up yourself.",
               link, base, f"{key}needs:{job.updated_at.timestamp():.0f}")
    elif state == S.WAITING_FOR_USER:
        notify(job.user, K.JOB_QUESTION, f"The agent has a question about {site}", "It is waiting for your answer.",
               link, base, f"{key}question:{job.updated_at.timestamp():.0f}")
