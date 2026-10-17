"""
The agent asking the user for something mid-job ("what is your constituency?").

Flow: the agent calls user.ask -> if the user already saved that detail it is used
without bothering them; otherwise an AgentQuestion is created, the job moves to
WAITING_FOR_USER, and the worker waits (browser still open) for the answer from the
web UI or an MCP client. A timeout or "skip" comes back to the agent as unanswered.
"""
import time

from django.conf import settings
from django.utils import timezone

from apps.common.db import ensure_db_connection
from apps.profiles import standard_fields as sf
from apps.profiles.models import ProfileEntry
from apps.registration.models import AgentQuestion, RegistrationJob

POLL_SECONDS = 1.5


def lookup_saved(user, key: str) -> str | None:
    key = sf.normalize_key(key)
    if not key:
        return None
    entry = ProfileEntry.objects.filter(user=user, key=key).first()
    return entry.get_value() if entry else None


def ask_user(job: RegistrationJob, question: str, key: str = "", options: list[str] | None = None,
             sensitive: bool = False) -> dict:
    key = sf.normalize_key(key)
    if key and sf.is_blocked_key(key):
        return {"answered": False, "reason": "Passwords and similar secrets are never requested from the user."}

    saved = lookup_saved(job.user, key)
    if saved is not None:
        return {"answered": True, "answer": saved, "source": "saved"}

    wait = getattr(settings, "HUMAN_ASSIST_TIMEOUT_SECONDS", 0)
    if wait <= 0:
        return {"answered": False, "reason": "Asking the user is turned off on this server."}

    q = AgentQuestion.objects.create(
        job=job, key=key, question=question[:500], options=list(options or [])[:30], sensitive=sensitive
    )
    previous_state = job.state
    job.state = RegistrationJob.State.WAITING_FOR_USER
    job.save(update_fields=["state", "updated_at"])

    deadline = time.monotonic() + wait
    try:
        while True:
            ensure_db_connection()
            q.refresh_from_db()
            job.refresh_from_db(fields=["state"])
            if job.state in RegistrationJob.TERMINAL_STATES:
                return {"answered": False, "cancelled": True, "reason": "The job was cancelled."}
            if q.status == AgentQuestion.Status.ANSWERED:
                return {"answered": True, "answer": q.get_answer(), "source": "user"}
            if q.status == AgentQuestion.Status.SKIPPED:
                return {"answered": False, "reason": "The user chose not to provide this."}
            if time.monotonic() >= deadline:
                q.status = AgentQuestion.Status.SKIPPED
                q.save(update_fields=["status", "updated_at"])
                return {"answered": False, "reason": "The user did not answer in time."}
            time.sleep(POLL_SECONDS)
    finally:
        job.refresh_from_db(fields=["state"])
        if job.state == RegistrationJob.State.WAITING_FOR_USER:
            job.state = previous_state if previous_state != RegistrationJob.State.QUEUED else RegistrationJob.State.ANALYZING
            job.save(update_fields=["state", "updated_at"])


def record_answer(question: AgentQuestion, answer: str | None, remember: bool) -> AgentQuestion:
    """Store the user's answer (or skip). Optionally remember it as a saved detail."""
    if answer is None or not answer.strip():
        question.status = AgentQuestion.Status.SKIPPED
        question.save(update_fields=["status", "updated_at"])
        return question
    question.set_answer(answer.strip())
    question.status = AgentQuestion.Status.ANSWERED
    question.answered_at = timezone.now()
    question.save(update_fields=["encrypted_answer", "status", "answered_at", "updated_at"])
    if remember and question.key and not sf.is_blocked_key(question.key):
        ProfileEntry.save_value(
            question.job.user, question.key, answer.strip(), label=question.question[:150], source="answer"
        )
    return question
