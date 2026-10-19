import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("apps.notifications")

WARN_HOURS = 24


@shared_task
def remind_expiring_accounts():
    """Tell the user a vault account (and its mailbox) will be wiped within a day."""
    from apps.accounts.models import TemporaryAccount
    from apps.notifications.models import Notification
    from apps.notifications.service import notify

    now = timezone.now()
    soon = now + timedelta(hours=WARN_HOURS)
    accounts = TemporaryAccount.objects.filter(
        status=TemporaryAccount.Status.ACTIVE,
        identity__expires_at__gt=now, identity__expires_at__lte=soon,
        job__account_mode="temporary",
    ).select_related("identity", "website", "job__user")
    sent = 0
    for account in accounts:
        when = account.identity.expires_at
        made = notify(
            account.job.user, Notification.Kind.ACCOUNT_EXPIRING,
            f"Your {account.website.domain} account expires soon",
            f"It and its mailbox will be erased on {when:%d %b %Y, %H:%M} UTC. Save what you need.",
            f"/accounts/{account.id}", {"account_id": str(account.id), "domain": account.website.domain},
            f"expiring:{account.id}",
        )
        sent += 1 if made else 0
    logger.info("remind_expiring_accounts: %d reminder(s)", sent)
    return sent
