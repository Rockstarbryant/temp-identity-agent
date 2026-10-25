"""Background mailbox polling (Celery beat). New mail becomes a notification."""
import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger("apps.email_service")

RECENT_DAYS = 3
BATCH = 100


@shared_task
def poll_mailboxes():
    """
    Check the mailboxes behind the user's vault accounts and running jobs. Recent ones every
    run; older ones only every ten minutes, so a big vault doesn't hammer the mail provider.
    """
    from apps.email_service.models import TemporaryEmail
    from apps.email_service.service import poll_mailbox

    from apps.email_service.inbox import skipped_own_mailbox_ids

    now = timezone.now()
    recent_cutoff = now - timedelta(seconds=45)
    old_cutoff = now - timedelta(minutes=10)
    young = now - timedelta(days=RECENT_DAYS)

    boxes = (
        TemporaryEmail.objects.filter(status=TemporaryEmail.Status.ACTIVE, expires_at__gt=now)
        .exclude(encrypted_credential="")
        .exclude(id__in=skipped_own_mailbox_ids(now))  # one check per connected inbox; none when muted
        .filter(
            Q(created_at__gte=young, last_polled_at__isnull=True)
            | Q(created_at__gte=young, last_polled_at__lt=recent_cutoff)
            | Q(created_at__lt=young, last_polled_at__lt=old_cutoff)
            | Q(created_at__lt=young, last_polled_at__isnull=True)
        )
        .select_related("identity")
        .order_by("last_polled_at")[:BATCH]
    )
    found = sum(poll_mailbox(b) for b in boxes)
    logger.info("poll_mailboxes: %d new message(s)", found)
    return found
