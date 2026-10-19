"""Creating and querying notifications. Nothing here may ever break the caller."""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications.models import Notification

logger = logging.getLogger("apps.notifications")

MAX_KEPT = 300  # per user; older ones are trimmed when new ones arrive


def notify(user, kind: str, title: str, body: str = "", link: str = "", data: dict | None = None,
           dedupe_key: str = "") -> Notification | None:
    """Create a notification. Returns None if it was a duplicate or something went wrong."""
    try:
        with transaction.atomic():
            note = Notification.objects.create(
                user=user, kind=kind, title=title[:200], body=(body or "")[:500],
                link=link[:200], data=data or {}, dedupe_key=dedupe_key[:120],
            )
    except IntegrityError:
        return None  # same dedupe_key already announced
    except Exception:  # noqa: BLE001 - a notification problem must never fail a job or a sync
        logger.exception("Could not create notification %s for user %s", kind, getattr(user, "id", user))
        return None
    _trim(user)
    return note


def _trim(user) -> None:
    try:
        ids = list(Notification.objects.filter(user=user).values_list("id", flat=True)[MAX_KEPT:MAX_KEPT + 1])
        if ids:
            Notification.objects.filter(user=user, id__lte=ids[0]).delete()
    except Exception:  # noqa: BLE001
        logger.exception("Could not trim notifications for user %s", getattr(user, "id", user))


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def serialize(n: Notification) -> dict:
    return {
        "id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
        "data": n.data, "read": n.read_at is not None, "created_at": n.created_at.isoformat(),
    }


def mark_read(user, ids: list[int] | None = None) -> int:
    qs = Notification.objects.filter(user=user, read_at__isnull=True)
    if ids is not None:
        qs = qs.filter(id__in=ids)
    return qs.update(read_at=timezone.now())
