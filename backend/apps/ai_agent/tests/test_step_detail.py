from unittest.mock import MagicMock, patch

import pytest

from ai.base import AIProvider
from ai.schemas import ChatMessage, CompletionResult, ToolCallRequest
from apps.ai_agent.step_detail import describe_step, index_elements, redact_for_storage
from apps.registration.models import RegistrationJob, RegistrationStep, TargetWebsite

EMAIL = {"element_id": "e1", "tag": "input", "type": "email", "label": "Email", "name": "email"}
PASSWORD = {"element_id": "e2", "tag": "input", "type": "password", "label": "Password", "value": "Sup3r!"}
BUTTON = {"element_id": "e3", "tag": "button", "label": "Sign up"}
LINK = {"element_id": "e4", "tag": "a", "href": "/login", "label": "Log in"}
OK = {"success": True, "result": {}}


class TestDescribe:
    def test_click_names_the_button(self):
        assert describe_step("browser.click", {"element_id": "e3"}, BUTTON, OK) == "Clicked the “Sign up” button"

    def test_click_on_link_says_link(self):
        assert describe_step("browser.click", {"element_id": "e4"}, LINK, OK) == "Clicked the “Log in” link"

    def test_type_shows_label_and_value(self):
        text = describe_step("browser.type", {"element_id": "e1", "text": "a@b.co"}, EMAIL, OK)
        assert text == "Filled “Email” with a@b.co"

    def test_password_value_never_shown(self):
        text = describe_step("browser.type", {"element_id": "e2", "text": "Sup3r!"}, PASSWORD, OK)
        assert "Sup3r!" not in text and "hidden" in text

    def test_secretish_label_is_hidden_even_if_type_text(self):
        el = {"element_id": "e9", "tag": "input", "type": "text", "label": "Confirm password"}
        assert "hidden" in describe_step("browser.type", {"element_id": "e9", "text": "zzz"}, el, OK)

    def test_failure_appends_error(self):
        out = {"success": False, "error": "element_id 'e3' not found"}
        assert "failed: element_id 'e3' not found" in describe_step("browser.click", {"element_id": "e3"}, None, out)

    def test_wait_for_verification_reports_no_email(self):
        out = {"success": True, "result": {"received": False}}
        text = describe_step("email.wait_for_verification", {"timeout_seconds": 60}, None, out)
        assert text == "No verification email arrived after 60s"


class TestRedaction:
    def test_typed_password_redacted_in_storage(self):
        args, _ = redact_for_storage("browser.type", {"element_id": "e2", "text": "Sup3r!"}, PASSWORD, OK)
        assert args["text"] == "[hidden]"

    def test_identity_password_and_snapshot_values_redacted(self):
        outcome = {"success": True, "result": {"password": "Sup3r!", "snapshot": {"elements": [dict(PASSWORD)]}}}
        _, safe = redact_for_storage("identity.get", {}, None, outcome)
        assert safe["result"]["password"] == "[hidden]"
        assert safe["result"]["snapshot"]["elements"][0]["value"] == "[hidden]"
        # the real outcome (what the model sees) is untouched
        assert outcome["result"]["password"] == "Sup3r!"

    def test_index_elements(self):
        out = {"success": True, "result": {"snapshot": {"elements": [EMAIL, BUTTON]}}}
        assert set(index_elements(out)) == {"e1", "e3"}


# --- Loop integration -----------------------------------------------------------

pytestmark_db = pytest.mark.django_db


class _Scripted(AIProvider):
    name = "scripted"

    def __init__(self, script):
        self.script = list(script)

    def complete(self, messages, tools):
        return self.script.pop(0)


class _FakeSession:
    def __init__(self, job, headless=True):
        self.page = MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _call(i, name, **args):
    return CompletionResult(message=ChatMessage(role="assistant", content="", tool_calls=[
        ToolCallRequest(id=f"c{i}", name=name, arguments=args)]))


@pytest.mark.django_db
class TestLoopIntegration:
    def _job(self, user, **kw):
        site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")
        return RegistrationJob.objects.create(user=user, target_website=site, max_steps=10, timeout_seconds=60, **kw)

    def _run(self, job, script, resume=False):
        with patch("apps.ai_agent.agent_loop.ManagedBrowserSession", _FakeSession), \
             patch("apps.ai_agent.agent_loop.get_ai_provider", return_value=_Scripted(script)):
            from apps.ai_agent.agent_loop import AgentRunner

            AgentRunner(job).run("https://example.com/register", resume=resume)

    def test_resume_continues_step_numbering_instead_of_colliding(self, user):
        job = self._job(user)
        self._run(job, [_call(1, "registration.mark_captcha_required", reason="reCAPTCHA")])
        job.refresh_from_db()
        assert job.state == "captcha_required"
        assert list(job.steps.values_list("step_index", flat=True)) == [0]

        job.state = "analyzing"
        job.save()
        self._run(job, [_call(2, "registration.mark_failed", reason="gave up")], resume=True)
        assert list(job.steps.values_list("step_index", flat=True)) == [0, 1]

    def test_steps_are_stored_with_detail(self, user):
        job = self._job(user)
        self._run(job, [_call(1, "registration.mark_failed", reason="nope")])
        step = RegistrationStep.objects.get(job=job)
        assert step.detail == "nope"
