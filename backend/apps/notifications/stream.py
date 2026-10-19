"""The Server-Sent Events generator behind GET /api/notifications/stream/."""
import json
import time

from django.conf import settings
from django.db import connection

from apps.notifications import service
from apps.notifications.models import Notification

TICK_SECONDS = 2.5
PING_EVERY = 15.0


def _sse(event: str, data, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n"


def _release_connection() -> None:
    # An idle stream must not hold a database connection between polls.
    if not connection.in_atomic_block:
        connection.close()


def stream(user, last_id: int, max_seconds: float | None = None, tick: float | None = None):
    """
    Yields SSE frames: `ready` first (with the unread count), then `notification` events for
    everything newer than `last_id`, plus a comment ping to keep proxies from closing the
    connection. Ends after STREAM_SECONDS so a worker thread is never held for long; the
    browser reconnects on its own and resumes from the last event id.
    """
    max_seconds = float(max_seconds if max_seconds is not None else getattr(settings, "NOTIFICATION_STREAM_SECONDS", 55))
    tick = TICK_SECONDS if tick is None else tick
    started = time.monotonic()
    last_ping = started
    last_mail_check = 0.0

    yield "retry: 3000\n\n"
    yield _sse("ready", {"unread": service.unread_count(user), "last_id": last_id})
    _release_connection()

    while time.monotonic() - started < max_seconds:
        now = time.monotonic()
        if now - last_mail_check > 30:
            last_mail_check = now
            try:
                from apps.email_service.service import poll_user_mailboxes

                poll_user_mailboxes(user, min_age_seconds=25)
            except Exception:  # noqa: BLE001 - a mail provider hiccup must not end the stream
                pass

        fresh = list(Notification.objects.filter(user=user, id__gt=last_id).order_by("id")[:50])
        for n in fresh:
            last_id = n.id
            yield _sse("notification", service.serialize(n), n.id)
        if fresh:
            yield _sse("unread", {"unread": service.unread_count(user)})
        _release_connection()

        if time.monotonic() - last_ping > PING_EVERY:
            last_ping = time.monotonic()
            yield ": ping\n\n"
        if tick:
            time.sleep(tick)
        else:
            break
