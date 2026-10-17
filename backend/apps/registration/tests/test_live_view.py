from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from apps.ai_agent.agent_loop import AgentRunner
from apps.browser import live_view
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def paused_job(user):
    site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/r")
    return RegistrationJob.objects.create(user=user, target_website=site, state="captcha_required")


class TestLiveEndpoints:
    def test_live_returns_frame_and_marks_viewer(self, auth_client, paused_job):
        cache.set(live_view._k(paused_job.id, "frame"),
                  {"seq": 3, "image": "abc", "width": 1024, "height": 768, "url": "https://x", "interactive": True})
        live_view.set_holding(paused_job.id)
        r = auth_client.get(f"/api/registration-jobs/{paused_job.id}/live/")
        assert r.status_code == 200
        body = r.json()
        assert body["interactive"] is True and body["seq"] == 3 and body["frame"]["image"] == "abc"
        assert live_view.has_viewer(paused_job.id)

    def test_live_omits_unchanged_frame(self, auth_client, paused_job):
        cache.set(live_view._k(paused_job.id, "frame"),
                  {"seq": 3, "image": "abc", "width": 1, "height": 1, "url": "u", "interactive": True})
        body = auth_client.get(f"/api/registration-jobs/{paused_job.id}/live/?since=3").json()
        assert body["frame"] is None and body["seq"] == 3

    def test_live_without_frame(self, auth_client, paused_job):
        body = auth_client.get(f"/api/registration-jobs/{paused_job.id}/live/").json()
        assert body["frame"] is None and body["interactive"] is False

    def test_other_users_job_is_404(self, auth_client, paused_job, other_user):
        paused_job.user = other_user
        paused_job.save()
        assert auth_client.get(f"/api/registration-jobs/{paused_job.id}/live/").status_code == 404

    def test_input_rejected_when_not_holding(self, auth_client, paused_job):
        r = auth_client.post(f"/api/registration-jobs/{paused_job.id}/live/input/",
                             {"type": "click", "x": 1, "y": 2}, format="json")
        assert r.status_code == 409

    def test_input_queued_when_holding(self, auth_client, paused_job):
        live_view.set_holding(paused_job.id)
        r = auth_client.post(f"/api/registration-jobs/{paused_job.id}/live/input/",
                             {"type": "click", "x": 10, "y": 20}, format="json")
        assert r.status_code == 202
        events = live_view.pop_inputs(paused_job.id)
        assert events and events[0]["type"] == "click" and events[0]["x"] == 10

    @pytest.mark.parametrize("payload", [
        {"type": "click"}, {"type": "key", "key": "F12"}, {"type": "type"},
        {"type": "scroll", "dy": 99999}, {"type": "nope"},
    ])
    def test_invalid_input_rejected(self, auth_client, paused_job, payload):
        live_view.set_holding(paused_job.id)
        r = auth_client.post(f"/api/registration-jobs/{paused_job.id}/live/input/", payload, format="json")
        assert r.status_code == 400

    def test_resume_while_holding_signals_done_without_new_task(self, auth_client, paused_job):
        live_view.set_holding(paused_job.id)
        with patch("apps.registration.views.resume_registration_job_task.delay") as delay:
            r = auth_client.post(f"/api/registration-jobs/{paused_job.id}/resume/")
        assert r.status_code == 202
        delay.assert_not_called()
        assert live_view.consume_done(paused_job.id)

    def test_resume_when_not_holding_enqueues_task(self, auth_client, paused_job):
        with patch("apps.registration.views.resume_registration_job_task.delay") as delay:
            r = auth_client.post(f"/api/registration-jobs/{paused_job.id}/resume/")
        assert r.status_code == 202
        delay.assert_called_once()


class TestApplyEvent:
    def _page(self):
        page = MagicMock()
        page.viewport_size = {"width": 1000, "height": 700}
        return page

    def test_click_is_clamped_to_viewport(self):
        page = self._page()
        live_view.apply_event(page, {"type": "click", "x": 5000, "y": 10})
        page.mouse.click.assert_called_once_with(1000, 10)

    def test_type_and_submit(self):
        page = self._page()
        live_view.apply_event(page, {"type": "type", "text": "abc", "submit": True})
        page.keyboard.type.assert_called_once()
        page.keyboard.press.assert_called_once_with("Enter")

    def test_disallowed_key_ignored(self):
        page = self._page()
        live_view.apply_event(page, {"type": "key", "key": "Control+a"})
        page.keyboard.press.assert_not_called()

    def test_scroll_clamped(self):
        page = self._page()
        live_view.apply_event(page, {"type": "scroll", "dy": 99999})
        page.mouse.wheel.assert_called_once_with(0, 1500)


class TestHold:
    def _runner(self, job):
        with patch("apps.ai_agent.agent_loop.get_ai_provider") as gp:
            gp.return_value = MagicMock(name="p", model="m")
            gp.return_value.name = "openrouter"
            return AgentRunner(job)

    def test_disabled_returns_false(self, paused_job, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 0
        assert self._runner(paused_job)._hold_for_human(MagicMock(), 0) is False

    def test_done_signal_resumes_in_same_browser(self, paused_job, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 5
        settings.LIVE_VIEW_TICK_SECONDS = 0
        session = MagicMock()
        runner = self._runner(paused_job)
        # A stale "done" from before the hold must not count; one sent during it does.
        live_view.signal_done(paused_job.id)
        with patch.object(live_view, "pop_inputs", side_effect=lambda j, limit=20: (live_view.signal_done(j), [])[1]):
            assert runner._hold_for_human(session, 0) is True
        paused_job.refresh_from_db()
        assert paused_job.state == "analyzing"
        assert not live_view.is_holding(paused_job.id)

    def test_applies_user_input_while_waiting(self, paused_job, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 5
        settings.LIVE_VIEW_TICK_SECONDS = 0
        session = MagicMock()
        session.page.viewport_size = {"width": 100, "height": 100}
        session.page.screenshot.return_value = b"jpeg"
        live_view.push_input(paused_job.id, {"type": "click", "x": 4, "y": 5})
        runner = self._runner(paused_job)
        original_pop = live_view.pop_inputs

        def pop_then_done(job_id, limit=20):
            events = original_pop(job_id, limit)
            live_view.signal_done(job_id)
            return events

        with patch.object(live_view, "pop_inputs", side_effect=pop_then_done):
            assert runner._hold_for_human(session, 0) is True
        session.page.mouse.click.assert_called_once_with(4, 5)

    def test_cancel_while_waiting_stops_hold(self, paused_job, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 5
        settings.LIVE_VIEW_TICK_SECONDS = 0
        RegistrationJob.objects.filter(id=paused_job.id).update(state="cancelled")
        assert self._runner(paused_job)._hold_for_human(MagicMock(), 0) is False
