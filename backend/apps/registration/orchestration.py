"""
Registration job orchestration.

This is what a Celery task actually calls — it wraps AgentRunner with
everything that has to happen around it: domain policy enforcement,
per-user concurrency/quota limits, state transitions into/out of
STARTING, and turning any exception into a properly-coded FAILED job
instead of leaving it stuck or crashing the worker.
"""
import logging

from django.conf import settings
from django.utils import timezone

from apps.ai_agent.agent_loop import AgentRunner
from apps.audit.models import AuditLog
from apps.common.db import ensure_db_connection
from apps.common.exceptions import (
    DomainBlockedError,
    RateLimitedError,
    TempIdentityAgentError,
    UnsupportedWebsiteError,
)
from apps.registration.models import DomainPolicy, RegistrationJob

logger = logging.getLogger("apps.registration")


def _fail(job: RegistrationJob, code: str, message: str) -> RegistrationJob:
    job.state = RegistrationJob.State.FAILED
    job.error_code = code
    job.error_message = message
    job.completed_at = timezone.now()
    job.save(update_fields=["state", "error_code", "error_message", "completed_at", "updated_at"])
    return job


def check_domain_policy(job: RegistrationJob) -> None:
    """
    Raises DomainBlockedError / UnsupportedWebsiteError, or transitions the
    job straight to HUMAN_ACTION_REQUIRED, based on the admin-configured
    DomainPolicy for this job's target domain. No matching row = allowed
    by default (admins block problematic domains, not allowlist everything).
    """
    domain = job.target_website.domain
    policy = DomainPolicy.objects.filter(domain=domain).first()
    if policy is None:
        return

    if policy.status == DomainPolicy.Status.BLOCKED:
        raise DomainBlockedError(policy.reason or f"{domain} is blocked by policy.")
    if policy.status == DomainPolicy.Status.UNSUPPORTED:
        raise UnsupportedWebsiteError(policy.reason or f"{domain} is not supported.")
    if policy.status == DomainPolicy.Status.REQUIRES_HUMAN:
        job.state = RegistrationJob.State.HUMAN_ACTION_REQUIRED
        job.error_code = "HUMAN_ACTION_REQUIRED"
        job.error_message = policy.reason or f"{domain} requires manual handling by policy."
        job.save(update_fields=["state", "error_code", "error_message", "updated_at"])
        raise _StopForHuman()


class _StopForHuman(Exception):
    """Internal signal — job was routed to HUMAN_ACTION_REQUIRED by policy, not a failure."""


def check_rate_limits(job: RegistrationJob) -> None:
    """Raises RateLimitedError if the user is over concurrency or daily quota."""
    active_count = (
        RegistrationJob.objects.filter(user=job.user, state__in=RegistrationJob.ACTIVE_STATES)
        .exclude(id=job.id)
        .count()
    )
    if active_count >= settings.MAX_CONCURRENT_JOBS:
        raise RateLimitedError(
            f"You already have {active_count} job(s) in progress "
            f"(limit: {settings.MAX_CONCURRENT_JOBS})."
        )

    today_count = RegistrationJob.objects.filter(
        user=job.user, created_at__date=timezone.now().date()
    ).count()
    if today_count > settings.MAX_JOBS_PER_USER_PER_DAY:
        raise RateLimitedError(
            f"Daily job limit reached ({settings.MAX_JOBS_PER_USER_PER_DAY}/day)."
        )


def start_registration_job(job_id) -> RegistrationJob:
    """Entry point called by the Celery task for a freshly-QUEUED job."""
    job = RegistrationJob.objects.select_related("user", "target_website").get(id=job_id)

    if job.state != RegistrationJob.State.QUEUED:
        logger.info("start_registration_job: job %s not QUEUED (state=%s), skipping.", job.id, job.state)
        return job

    try:
        check_domain_policy(job)
        check_rate_limits(job)
    except _StopForHuman:
        return job
    except DomainBlockedError as exc:
        return _fail(job, "DOMAIN_BLOCKED", exc.message)
    except UnsupportedWebsiteError as exc:
        return _fail(job, "UNSUPPORTED_WEBSITE", exc.message)
    except RateLimitedError as exc:
        return _fail(job, "RATE_LIMITED", exc.message)

    job.state = RegistrationJob.State.STARTING
    job.started_at = timezone.now()
    job.save(update_fields=["state", "started_at", "updated_at"])

    try:
        AgentRunner(job).run(job.target_website.registration_url, resume=False)
    except TempIdentityAgentError as exc:
        ensure_db_connection()
        job.refresh_from_db()
        if job.state not in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
            _fail(job, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001 — never let an unexpected error leave a job stuck
        logger.exception("Unhandled error running job %s", job.id)
        ensure_db_connection()
        job.refresh_from_db()
        if job.state not in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
            _fail(job, "AI_ERROR", f"Unexpected error: {exc}")

    ensure_db_connection()
    job.refresh_from_db()
    AuditLog.objects.create(
        user=job.user, action="job.finished", resource_type="RegistrationJob",
        resource_id=str(job.id), metadata={"final_state": job.state},
    )
    return job


def resume_registration_job(job_id) -> RegistrationJob:
    """Entry point called after a user confirms they've cleared a CAPTCHA/human-action step."""
    job = RegistrationJob.objects.select_related("user", "target_website").get(id=job_id)

    if job.state not in RegistrationJob.RESUMABLE_STATES:
        raise TempIdentityAgentError(
            f"Job {job.id} is in state {job.state!r}, which cannot be resumed."
        )

    job.state = RegistrationJob.State.ANALYZING
    job.error_code = ""
    job.error_message = ""
    job.save(update_fields=["state", "error_code", "error_message", "updated_at"])

    try:
        AgentRunner(job).run(job.target_website.registration_url, resume=True)
    except TempIdentityAgentError as exc:
        ensure_db_connection()
        job.refresh_from_db()
        if job.state not in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
            _fail(job, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error resuming job %s", job.id)
        ensure_db_connection()
        job.refresh_from_db()
        if job.state not in RegistrationJob.TERMINAL_STATES | RegistrationJob.RESUMABLE_STATES:
            _fail(job, "AI_ERROR", f"Unexpected error: {exc}")

    ensure_db_connection()
    job.refresh_from_db()
    return job


def cancel_registration_job(job_id) -> RegistrationJob:
    """User-requested cancellation. Only valid for non-terminal jobs."""
    job = RegistrationJob.objects.get(id=job_id)
    if job.state in RegistrationJob.TERMINAL_STATES:
        raise TempIdentityAgentError(f"Job {job.id} is already {job.state} and cannot be cancelled.")

    job.state = RegistrationJob.State.CANCELLED
    job.completed_at = timezone.now()
    job.save(update_fields=["state", "completed_at", "updated_at"])
    AuditLog.objects.create(
        user=job.user, action="job.cancelled", resource_type="RegistrationJob", resource_id=str(job.id)
    )
    return job
