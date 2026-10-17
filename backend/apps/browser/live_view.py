"""
Live browser view: lets the user see (and, when the agent is stuck, drive) the
server-side browser from the job page.

Why this exists: the agent's browser runs headless in a Celery worker on the
server, so a CAPTCHA or other manual step can't be completed on the user's own
device. While a job is paused, the worker keeps its browser open and:

  * publishes screenshots (JPEG) for the web process to serve,
  * applies the user's taps / typing / scrolling, sent through a small queue,
  * continues the agent in the *same* browser when the user presses Continue.

The worker and the web process are different processes, so everything is
exchanged through the shared Django cache (Redis in production). Frames and
flags are cached with short TTLs; the input queue uses a Redis list when
available and falls back to a plain cache entry (single-process / dev).

Nothing here solves a CAPTCHA automatically. A human does it.
"""
import base64
import hashlib
import json
import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("apps.browser")

HOLDING_TTL = 20      # seconds; the worker refreshes this while it waits
FRAME_TTL = 60
VIEWER_TTL = 6        # a viewer counts as present for this long after a poll
INPUT_TTL = 60
INPUT_MAX = 100       # queued events kept; older ones are dropped
ALLOWED_KEYS = frozenset(
    {"Enter", "Tab", "Backspace", "Delete", "Escape", "Space",
     "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"}
)
MAX_TEXT = 300
MAX_SCROLL = 1500


def _k(job_id, name: str) -> str:
    return f"live:{job_id}:{name}"


def _redis():
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if "django_redis" not in backend:
        return None
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception:  # noqa: BLE001
        logger.warning("Redis connection unavailable for live view; falling back to cache entry.")
        return None


# --- flags ---------------------------------------------------------------------

def set_holding(job_id) -> None:
    cache.set(_k(job_id, "holding"), 1, HOLDING_TTL)


def clear_holding(job_id) -> None:
    cache.delete(_k(job_id, "holding"))


def is_holding(job_id) -> bool:
    return bool(cache.get(_k(job_id, "holding")))


def mark_viewer(job_id) -> None:
    cache.set(_k(job_id, "viewer"), 1, VIEWER_TTL)


def has_viewer(job_id) -> bool:
    return bool(cache.get(_k(job_id, "viewer")))


def signal_done(job_id) -> None:
    cache.set(_k(job_id, "done"), 1, 60)


def consume_done(job_id) -> bool:
    key = _k(job_id, "done")
    if cache.get(key):
        cache.delete(key)
        return True
    return False


def clear_done(job_id) -> None:
    cache.delete(_k(job_id, "done"))


# --- frames --------------------------------------------------------------------

class FramePublisher:
    """Captures the page and publishes a frame, skipping identical consecutive frames."""

    def __init__(self, job_id):
        self.job_id = job_id
        self.seq = 0
        self._last_hash = ""

    def reset(self) -> None:
        self._last_hash = ""

    def publish(self, page, interactive: bool = False) -> bool:
        jpeg = page.screenshot(type="jpeg", quality=60)
        digest = hashlib.sha1(jpeg).hexdigest()
        size = page.viewport_size or {}
        if digest == self._last_hash:
            return False
        self._last_hash = digest
        self.seq += 1
        cache.set(
            _k(self.job_id, "frame"),
            {
                "seq": self.seq,
                "image": base64.b64encode(jpeg).decode("ascii"),
                "width": int(size.get("width", 0) or 0),
                "height": int(size.get("height", 0) or 0),
                "url": str(page.url)[:300],
                "interactive": interactive,
            },
            FRAME_TTL,
        )
        return True


def get_frame(job_id) -> dict[str, Any] | None:
    return cache.get(_k(job_id, "frame"))


def clear_frame(job_id) -> None:
    cache.delete(_k(job_id, "frame"))


# --- input queue ---------------------------------------------------------------

def push_input(job_id, event: dict[str, Any]) -> None:
    payload = json.dumps(event)
    r = _redis()
    if r is not None:
        key = f"tia:{_k(job_id, 'input')}"
        pipe = r.pipeline()
        pipe.rpush(key, payload)
        pipe.ltrim(key, -INPUT_MAX, -1)
        pipe.expire(key, INPUT_TTL)
        pipe.execute()
        return
    key = _k(job_id, "input")
    items = cache.get(key) or []
    items.append(event)
    cache.set(key, items[-INPUT_MAX:], INPUT_TTL)


def pop_inputs(job_id, limit: int = 20) -> list[dict[str, Any]]:
    r = _redis()
    events: list[dict[str, Any]] = []
    if r is not None:
        key = f"tia:{_k(job_id, 'input')}"
        for _ in range(limit):
            raw = r.lpop(key)
            if raw is None:
                break
            try:
                events.append(json.loads(raw))
            except (TypeError, ValueError):
                continue
        return events
    key = _k(job_id, "input")
    items = cache.get(key) or []
    if items:
        cache.delete(key)
    return items[:limit]


# --- applying input to the page ------------------------------------------------

def apply_event(page, event: dict[str, Any]) -> None:
    """Replay one validated user event in the browser. Unknown events are ignored."""
    kind = event.get("type")
    size = page.viewport_size or {}
    max_x, max_y = int(size.get("width", 1280) or 1280), int(size.get("height", 800) or 800)

    if kind == "click":
        x = min(max(int(event.get("x", 0)), 0), max_x)
        y = min(max(int(event.get("y", 0)), 0), max_y)
        page.mouse.click(x, y)
    elif kind == "type":
        text = str(event.get("text", ""))[:MAX_TEXT]
        if text:
            page.keyboard.type(text, delay=25)
        if event.get("submit"):
            page.keyboard.press("Enter")
    elif kind == "key":
        key = event.get("key")
        if key in ALLOWED_KEYS:
            page.keyboard.press(key)
    elif kind == "scroll":
        dy = min(max(int(event.get("dy", 0)), -MAX_SCROLL), MAX_SCROLL)
        page.mouse.wheel(0, dy)
