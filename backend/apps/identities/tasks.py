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
        TemporaryAccount.objects.filter(identity=identity).exclude(
            status=TemporaryAccount.Status.DELETED
        ).update(status=TemporaryAccount.Status.EXPIRED)
        count += 1

    logger.info("expire_temporary_identities: expired %d identities", count)
    return count


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
