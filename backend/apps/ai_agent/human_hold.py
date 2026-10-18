"""Pause a job so the user can drive the agent's browser from the live view."""
import time

from django.conf import settings

from apps.browser import live_view
from apps.common.db import ensure_db_connection
from apps.registration.models import RegistrationJob


def hold_for_human(job: RegistrationJob, session, frames: live_view.FramePublisher) -> bool:
    """
    The job is paused for a CAPTCHA / sign-in / manual step. Keep this browser open,
    stream it to the live view, apply the user's input, and wait.

    Returns True if the user pressed Continue (job moved back to ANALYZING),
    False if the wait ended some other way (timeout, cancelled, disabled).
    """
    max_wait = getattr(settings, "HUMAN_ASSIST_TIMEOUT_SECONDS", 0)
    if max_wait <= 0:
        return False
    tick = max(getattr(settings, "LIVE_VIEW_TICK_SECONDS", 0.6), 0)
    job_id = job.id
    live_view.clear_done(job_id)
    live_view.set_holding(job_id)
    idle_ticks = 0
    end = time.monotonic() + max_wait
    try:
        while time.monotonic() < end:
            ensure_db_connection()
            job.refresh_from_db(fields=["state"])
            if job.state not in RegistrationJob.RESUMABLE_STATES:
                return False  # cancelled (or otherwise changed) while waiting
            if live_view.consume_done(job_id):
                job.state = RegistrationJob.State.ANALYZING
                job.error_code = ""
                job.error_message = ""
                job.save(update_fields=["state", "error_code", "error_message", "updated_at"])
                return True

            live_view.set_holding(job_id)
            changed = False
            for event in live_view.pop_inputs(job_id):
                try:
                    live_view.apply_event(session.page, event)
                    changed = True
                except Exception:  # noqa: BLE001 - one bad tap must not end the wait
                    continue
            if live_view.has_viewer(job_id) or changed or idle_ticks % 8 == 0:
                try:
                    frames.publish(session.page, interactive=True)
                except Exception:  # noqa: BLE001
                    pass
            idle_ticks += 1
            time.sleep(tick)
        return False
    finally:
        live_view.clear_holding(job_id)
        live_view.clear_frame(job_id)
        frames.reset()
