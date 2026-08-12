"""Celery tasks for registration jobs. Thin wrappers around apps.registration.orchestration."""
import logging

from celery import shared_task

logger = logging.getLogger("apps.registration")


@shared_task(bind=True, max_retries=0, time_limit=None)
def run_registration_job_task(self, job_id):
    """
    Runs a freshly-queued job to completion or a stopping state.

    No automatic retries: a failed/paused job is a normal, expected
    outcome (see architecture.md's error taxonomy), not something to
    silently retry and potentially hammer the target site.
    """
    from apps.registration.orchestration import start_registration_job

    job = start_registration_job(job_id)
    logger.info("run_registration_job_task finished job %s in state %s", job_id, job.state)
    return str(job.id)


@shared_task(bind=True, max_retries=0)
def resume_registration_job_task(self, job_id):
    from apps.registration.orchestration import resume_registration_job

    job = resume_registration_job(job_id)
    logger.info("resume_registration_job_task finished job %s in state %s", job_id, job.state)
    return str(job.id)
