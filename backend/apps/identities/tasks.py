"""
Retention / expiration cleanup — run on a schedule via Celery beat
(see CELERY_BEAT_SCHEDULE in config/settings/base.py).

Per architecture.md section 18: expired identities get their
credentials wiped (not just status-flagged) so nothing sensitive sits
around past its retention window.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("apps.identities")


@shared_task
def expire_temporary_identities():
    """
    Find identities past their expiration and scrub them: blank the
    encrypted password (not just mark expired — actually remove the
    secret), mark associated mailboxes/accounts expired too.
    """
    from apps.accounts.models import TemporaryAccount
    from apps.email_service.models import TemporaryEmail
    from apps.identities.models import TemporaryIdentity

    now = timezone.now()
    expired_identities = TemporaryIdentity.objects.filter(
        status=TemporaryIdentity.Status.ACTIVE, expires_at__lte=now
    )

    count = 0
    for identity in expired_identities.iterator():
        identity.encrypted_password = ""  # scrub the secret, don't just flag it
        identity.status = TemporaryIdentity.Status.EXPIRED
        identity.save(update_fields=["encrypted_password", "status", "updated_at"])

        TemporaryEmail.objects.filter(identity=identity, status=TemporaryEmail.Status.ACTIVE).update(
            status=TemporaryEmail.Status.EXPIRED, encrypted_credential=""
        )
        from apps.email_service.models import EmailMessage

        EmailMessage.objects.filter(mailbox__identity=identity).delete()  # erase the inbox with the account
        affected = list(
            TemporaryAccount.objects.filter(identity=identity)
            .exclude(status=TemporaryAccount.Status.DELETED).select_related("website", "job__user")
        )
        TemporaryAccount.objects.filter(pk__in=[a.pk for a in affected]).update(
            status=TemporaryAccount.Status.EXPIRED
        )
        _announce_expired(affected)
        count += 1

    logger.info("expire_temporary_identities: expired %d identities", count)
    return count


def _announce_expired(accounts) -> None:
    from apps.notifications.models import Notification
    from apps.notifications.service import notify

    for account in accounts:
        notify(
            account.job.user, Notification.Kind.ACCOUNT_EXPIRED, f"Your {account.website.domain} account expired",
            "The account and its mailbox were erased.", "/accounts",
            {"account_id": str(account.id), "domain": account.website.domain}, f"expired:{account.id}",
        )


@shared_task
def expire_stale_registration_jobs():
    """
    Safety net: jobs stuck in a non-terminal state well past their own
    timeout (e.g. a worker crashed mid-job) get force-marked EXPIRED so
    they don't silently count against a user's concurrency quota forever.
    """
    from datetime import timedelta

    from apps.registration.models import RegistrationJob

    cutoff = timezone.now() - timedelta(hours=2)
    stale = RegistrationJob.objects.filter(
        state__in=RegistrationJob.ACTIVE_STATES, updated_at__lt=cutoff
    )
    count = stale.update(state=RegistrationJob.State.EXPIRED, completed_at=timezone.now())
    logger.info("expire_stale_registration_jobs: force-expired %d stuck jobs", count)
    return count


@shared_task
def close_orphaned_browser_sessions():
    """Mark any BrowserSession left OPEN with no activity as crashed/closed."""
    from datetime import timedelta

    from apps.browser.models import BrowserSession

    cutoff = timezone.now() - timedelta(hours=1)
    count = BrowserSession.objects.filter(
        status=BrowserSession.Status.OPEN, updated_at__lt=cutoff
    ).update(status=BrowserSession.Status.CRASHED, ended_at=timezone.now())
    return count


@shared_task
def fail_stalled_registration_jobs():
    """
    A job that is 'running' but has shown no sign of life (no new step, no state change) for
    longer than its time budget lost its worker (restart, network drop, crash). Mark it failed
    so the person sees an answer and can retry, instead of 'Starting' forever.
    Jobs waiting on a person (a question, CAPTCHA) are left alone.
    """
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Max

    from apps.registration.models import RegistrationJob

    S = RegistrationJob.State
    running = [S.STARTING, S.OPENING_SITE, S.ANALYZING, S.IDENTITY_CREATED, S.FILLING_FORM,
               S.SUBMITTING, S.WAITING_FOR_EMAIL, S.VERIFYING]
    cutoff = timezone.now() - timedelta(seconds=settings.MAX_JOB_DURATION_SECONDS + 180)
    count = 0
    candidates = (RegistrationJob.objects.filter(state__in=running, updated_at__lt=cutoff)
                  .annotate(last_step=Max("steps__created_at")))
    for job in candidates:
        if job.last_step and job.last_step >= cutoff:
            continue
        job.state = S.FAILED
        job.error_code = "WORKER_LOST"
        job.error_message = ("The task stopped before it finished (the worker lost its connection). "
                             "Nothing was lost. Press Try again.")
        job.completed_at = timezone.now()
        job.save(update_fields=["state", "error_code", "error_message", "completed_at", "updated_at"])
        count += 1
    if count:
        logger.warning("fail_stalled_registration_jobs: failed %d stalled jobs", count)
    return count
