import json
from unittest.mock import MagicMock, patch

import pytest

from ai.prompts.system_prompt import build_system_prompt
from ai.schemas import ChatMessage, ToolCallRequest
from apps.ai_agent import questions
from apps.ai_agent.agent_loop import compress_old_snapshots
from apps.ai_agent.context import AgentContext
from apps.ai_agent.dispatcher import dispatch_tool_call
from apps.ai_agent.step_detail import describe_step, redact_for_storage
from apps.profiles.models import EmailConnection, ProfileEntry
from apps.registration.models import AgentQuestion, RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture
def site():
    return TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")


def make_job(user, site, **kw):
    return RegistrationJob.objects.create(user=user, target_website=site, state="analyzing", **kw)


def call(ctx, name, **args):
    return dispatch_tool_call(ctx, ToolCallRequest(id="1", name=name, arguments=args))


class TestAskUser:
    def test_saved_detail_is_used_without_asking(self, user, site):
        ProfileEntry.save_value(user, "phone", "0712345678")
        job = make_job(user, site)
        out = questions.ask_user(job, "What is your phone number?", key="phone")
        assert out == {"answered": True, "answer": "0712345678", "source": "saved"}
        assert not AgentQuestion.objects.exists()

    def test_disabled_when_wait_is_zero(self, user, site, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 0
        out = questions.ask_user(make_job(user, site), "Constituency?", key="constituency")
        assert out["answered"] is False

    def test_waits_for_answer_then_restores_state(self, user, site, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 30
        job = make_job(user, site)
        seen = {}

        def answer_during_sleep(_):
            q = AgentQuestion.objects.get()
            seen["state"] = RegistrationJob.objects.get(id=job.id).state
            seen["pending"] = q.status
            questions.record_answer(q, "Westlands", remember=True)

        with patch("apps.ai_agent.questions.time.sleep", side_effect=answer_during_sleep):
            out = questions.ask_user(job, "Which constituency?", key="Home Constituency", options=["Westlands"])
        assert out == {"answered": True, "answer": "Westlands", "source": "user"}
        assert seen == {"state": "waiting_for_user", "pending": "pending"}
        job.refresh_from_db()
        assert job.state == "analyzing"
        assert ProfileEntry.objects.get(user=user, key="home_constituency").get_value() == "Westlands"

    def test_answer_not_remembered_unless_asked(self, user, site, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 30
        job = make_job(user, site)
        with patch("apps.ai_agent.questions.time.sleep",
                   side_effect=lambda _: questions.record_answer(AgentQuestion.objects.get(), "x", remember=False)):
            questions.ask_user(job, "A question?", key="thing")
        assert not ProfileEntry.objects.exists()

    def test_skip_is_reported(self, user, site, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 30
        job = make_job(user, site)
        with patch("apps.ai_agent.questions.time.sleep",
                   side_effect=lambda _: questions.record_answer(AgentQuestion.objects.get(), None, remember=False)):
            out = questions.ask_user(job, "ID number?", key="national_id", sensitive=True)
        assert out["answered"] is False and "not to provide" in out["reason"]

    def test_timeout_marks_skipped(self, user, site, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 1
        job = make_job(user, site)
        with patch("apps.ai_agent.questions.time.sleep"), \
             patch("apps.ai_agent.questions.time.monotonic", side_effect=[0, 0, 5, 5, 5]):
            out = questions.ask_user(job, "Anything?", key="anything")
        assert out["answered"] is False
        assert AgentQuestion.objects.get().status == "skipped"

    def test_cancel_while_waiting(self, user, site, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 30
        job = make_job(user, site)
        with patch("apps.ai_agent.questions.time.sleep",
                   side_effect=lambda _: RegistrationJob.objects.filter(id=job.id).update(state="cancelled")):
            out = questions.ask_user(job, "Anything?", key="anything")
        assert out.get("cancelled") is True

    def test_passwords_are_never_asked(self, user, site):
        out = questions.ask_user(make_job(user, site), "Your bank password?", key="bank_password")
        assert out["answered"] is False and not AgentQuestion.objects.exists()


class TestProfileTool:
    def test_names_only_then_values(self, user, site):
        ProfileEntry.save_value(user, "phone", "0712345678")
        ProfileEntry.save_value(user, "county", "Nairobi")
        ctx = AgentContext(job=make_job(user, site))
        names = call(ctx, "profile.get")["result"]
        assert {d["key"] for d in names["saved_details"]} == {"phone", "county"}
        assert "0712" not in json.dumps(names)
        vals = call(ctx, "profile.get", keys=["phone", "city"])["result"]
        assert vals == {"values": {"phone": "0712345678"}, "not_saved": ["city"]}

    def test_values_are_redacted_in_stored_steps(self):
        out = {"success": True, "result": {"values": {"phone": "0712345678"}, "not_saved": []}}
        _, safe = redact_for_storage("profile.get", {"keys": ["phone"]}, None, out)
        assert "0712345678" not in json.dumps(safe)


class TestAuthCheckGate:
    def test_mcp_job_cannot_fill_before_reporting(self, user, site):
        ctx = AgentContext(job=make_job(user, site, source="mcp"), session=MagicMock())
        assert "site.report_auth_methods" in call(ctx, "browser.type", element_id="x", text="a")["error"]
        assert "site.report_auth_methods" in call(ctx, "identity.create")["error"]

    def test_web_job_is_not_gated(self, user, site):
        ctx = AgentContext(job=make_job(user, site), session=MagicMock())
        with patch("apps.ai_agent.tools.browser_actions.browser_type") as bt:
            bt.return_value.model_dump.return_value = {"success": True}
            assert call(ctx, "browser.type", element_id="x", text="a")["success"] is True

    def test_social_only_site_stops_the_job(self, user, site):
        job = make_job(user, site, source="mcp")
        ctx = AgentContext(job=job)
        out = call(ctx, "site.report_auth_methods", email_password=False, methods=["google", "facebook"])
        assert out["result"]["proceed"] is False
        job.refresh_from_db()
        assert job.state == "failed" and job.error_code == "AUTH_METHOD_UNSUPPORTED"
        assert "email and password" in job.error_message and "google" in job.error_message

    def test_email_password_site_unlocks_filling(self, user, site):
        job = make_job(user, site, source="mcp")
        ctx = AgentContext(job=job, session=MagicMock())
        assert call(ctx, "site.report_auth_methods", email_password=True, methods=["email_password", "google"])["result"]["proceed"]
        job.refresh_from_db()
        assert job.state == "analyzing" and job.auth_check["email_password"] is True
        with patch("apps.ai_agent.tools.browser_actions.browser_type") as bt:
            bt.return_value.model_dump.return_value = {"success": True}
            assert call(AgentContext(job=job, session=MagicMock()), "browser.type", element_id="x", text="a")["success"]


class TestPermanentMode:
    def test_requires_connected_email(self, user, site):
        ctx = AgentContext(job=make_job(user, site, account_mode="permanent"))
        assert "no email is connected" in call(ctx, "identity.create")["error"]

    def test_uses_real_email_and_profile_name(self, user, site):
        conn = EmailConnection(user=user, kind="imap", address="me@gmail.com", imap_host="imap.gmail.com")
        conn.set_secret("pw")
        conn.save()
        ProfileEntry.save_value(user, "full_name", "Brian Ouma")
        imap = MagicMock()
        imap.status.return_value = ("OK", [b"INBOX (UIDNEXT 41)"])
        job = make_job(user, site, account_mode="permanent")
        ctx = AgentContext(job=job)
        with patch("apps.email_service.providers.user_imap.open_imap", return_value=imap):
            out = call(ctx, "identity.create")
        assert out["success"], out
        res = out["result"]
        assert res["email"] == "me@gmail.com" and res["name"] == "Brian Ouma" and res["permanent"] is True
        assert ctx.mailbox.provider == "imap"
        assert json.loads(ctx.mailbox.get_credential()) == {"connection_id": str(conn.id), "baseline_uid": 40}
        assert ctx.identity.get_password()  # generated, retrievable for the vault
        assert (ctx.identity.expires_at.year - 2026) >= 9  # effectively never expires
        job.refresh_from_db()
        assert job.identity_id == ctx.identity.id

    def test_gmail_baseline_is_a_timestamp(self, user, site):
        conn = EmailConnection(user=user, kind="gmail", address="me@gmail.com")
        conn.set_secret("rt")
        conn.save()
        ctx = AgentContext(job=make_job(user, site, account_mode="permanent"))
        out = call(ctx, "identity.create")
        assert out["success"]
        assert json.loads(ctx.mailbox.get_credential())["baseline_ts"] > 1_700_000_000

    def test_form_jobs_dont_create_identities(self, user, site):
        ctx = AgentContext(job=make_job(user, site, kind="form"))
        assert "fills in a form" in call(ctx, "identity.create")["error"]


class TestCompletionGates:
    def test_form_needs_report(self, user, site):
        job = make_job(user, site, kind="form")
        ctx = AgentContext(job=job)
        assert "form.complete" in call(ctx, "registration.mark_complete")["error"]
        out = call(ctx, "form.complete", submitted=[{"question": "Name", "answer": "Brian"}], note="Recorded")
        assert out["success"]
        job.refresh_from_db()
        assert job.state == "completed" and job.result["submitted"][0]["answer"] == "Brian"
        assert not hasattr(job, "account")  # no vault entry for a form

    def test_extraction_goal_requires_result(self, user, site):
        job = make_job(user, site, goal="my balance")
        ctx = AgentContext(job=job)
        assert "data.submit_result" in call(ctx, "registration.mark_complete")["error"]
        assert call(ctx, "data.submit_result", summary="Balance is 5", data={"balance": 5})["success"]
        assert call(ctx, "registration.mark_complete")["success"]
        job.refresh_from_db()
        assert job.result["data"] == {"balance": 5}

    def test_oversized_result_rejected(self, user, site):
        ctx = AgentContext(job=make_job(user, site))
        assert not call(ctx, "data.submit_result", summary="x", data={"a": "z" * 30000})["success"]


class TestStepDetail:
    def test_describe_new_tools(self):
        ok = {"success": True}
        assert "saved answer" in describe_step("user.ask", {"question": "Phone?"}, None, {**ok, "result": {"answered": True, "source": "saved", "answer": "x"}})
        assert "0712" in describe_step("user.ask", {"question": "Phone?"}, None, {**ok, "result": {"answered": True, "answer": "0712"}})
        hidden = describe_step("user.ask", {"question": "ID?", "sensitive": True}, None, {**ok, "result": {"answered": True, "answer": "12345678"}})
        assert "12345678" not in hidden and "hidden" in hidden
        assert "no answer" in describe_step("user.ask", {"question": "ID?"}, None, {**ok, "result": {"answered": False, "reason": "timeout"}})
        assert "email and password is supported" in describe_step("site.report_auth_methods", {"email_password": True}, None, ok)
        assert "google" in describe_step("site.report_auth_methods", {"email_password": False, "methods": ["google"]}, None, ok)
        assert "2 answers" in describe_step("form.complete", {"submitted": [1, 2]}, None, ok)

    def test_sensitive_and_saved_answers_redacted(self):
        out = {"success": True, "result": {"answered": True, "answer": "12345678", "source": "user"}}
        _, safe = redact_for_storage("user.ask", {"sensitive": True}, None, out)
        assert "12345678" not in json.dumps(safe)
        out["result"]["source"] = "saved"
        _, safe = redact_for_storage("user.ask", {}, None, out)
        assert "12345678" not in json.dumps(safe)


class TestPrompts:
    def _job(self, **kw):
        base = dict(kind="registration", account_mode="temporary", source="web", goal="")
        return MagicMock(**{**base, **kw})

    def test_all_prompts_forbid_inventing_details(self):
        for job in (self._job(), self._job(kind="form"), self._job(account_mode="permanent")):
            p = build_system_prompt(job)
            assert "NEVER invent personal details" in p and "user.ask" in p

    def test_mode_specific_text(self):
        assert "TEMPORARY" in build_system_prompt(self._job())
        assert "PERMANENT" in build_system_prompt(self._job(account_mode="permanent"))
        assert "form" in build_system_prompt(self._job(kind="form")).lower()
        assert "form.complete" in build_system_prompt(self._job(kind="form"))

    def test_mcp_prompt_has_auth_check_and_goal(self):
        p = build_system_prompt(self._job(source="mcp", goal="my invoices"))
        assert "site.report_auth_methods" in p and "my invoices" in p
        assert "site.report_auth_methods" not in build_system_prompt(self._job())


class TestSnapshotCompression:
    def _tool(self, i, n=3):
        snap = {"url": f"https://x/{i}", "title": f"T{i}", "elements": [{"element_id": f"e{j}"} for j in range(n)]}
        return ChatMessage(role="tool", tool_call_id=str(i), content=json.dumps({"success": True, "result": {"snapshot": snap}}))

    def test_only_latest_snapshot_stays_full(self):
        msgs = [ChatMessage(role="system", content="s"), self._tool(1), self._tool(2), self._tool(3)]
        compress_old_snapshots(msgs)
        assert "e0" not in msgs[1].content and "omitted" in msgs[1].content and "https://x/1" in msgs[1].content
        assert "omitted" in msgs[2].content
        assert "e0" in msgs[3].content

    def test_idempotent_and_ignores_other_messages(self):
        msgs = [ChatMessage(role="user", content='mentions "snapshot"'), self._tool(1), self._tool(2)]
        compress_old_snapshots(msgs)
        before = [m.content for m in msgs]
        compress_old_snapshots(msgs)
        assert [m.content for m in msgs] == before


# --- Whole loop ----------------------------------------------------------------

from ai.base import AIProvider  # noqa: E402
from ai.schemas import CompletionResult  # noqa: E402


class _Scripted(AIProvider):
    name = "scripted"

    def __init__(self, script):
        self.script = list(script)
        self.seen_messages = []

    def complete(self, messages, tools):
        self.seen_messages.append([m.model_copy() for m in messages])
        return self.script.pop(0)


class _Session:
    def __init__(self, job, headless=True):
        self.page = MagicMock()
        self.page.url = "https://docs.google.com/forms/d/e/X/viewform"
        self.page.title.return_value = "Form"
        self.page.evaluate.return_value = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def goto(self, url):
        self.page.url = url


def _calls(*calls):
    return CompletionResult(message=ChatMessage(role="assistant", content="", tool_calls=[
        ToolCallRequest(id=f"c{i}", name=n, arguments=a) for i, (n, a) in enumerate(calls)]))


def _run(job, script, url):
    from apps.ai_agent.agent_loop import AgentRunner

    provider = _Scripted(script)
    with patch("apps.ai_agent.agent_loop.ManagedBrowserSession", _Session), \
         patch("apps.ai_agent.agent_loop.get_ai_provider", return_value=provider):
        AgentRunner(job).run(url)
    job.refresh_from_db()
    return provider


class TestLoopIntegration:
    def test_form_job_reads_saved_details_and_reports_submission(self, user, site):
        ProfileEntry.save_value(user, "full_name", "Brian Ouma")
        job = make_job(user, site, kind="form", target_url="https://docs.google.com/forms/d/e/X/viewform")
        script = [
            _calls(("browser.open", {"url": job.target_url})),
            _calls(("profile.get", {})),
            _calls(("user.ask", {"question": "Full name?", "field_key": "full_name"})),
            _calls(("form.complete", {"submitted": [{"question": "Full name", "answer": "Brian Ouma"}], "note": "Recorded"})),
        ]
        provider = _run(job, script, job.target_url)
        assert job.state == "completed"
        assert job.result["submitted"] == [{"question": "Full name", "answer": "Brian Ouma"}]
        sys_prompt = provider.seen_messages[0][0].content
        assert "fills in and submits an online form" in sys_prompt
        details = list(job.steps.values_list("detail", flat=True))
        assert any("saved answer" in d for d in details) and any("Submitted the form" in d for d in details)
        assert not any("Brian Ouma" in str(s.tool_result) for s in job.steps.filter(tool_name="user.ask"))  # saved values aren't re-stored

    def test_mcp_job_stops_at_social_only_site(self, user, site):
        job = make_job(user, site, source="mcp", goal="my data")
        script = [
            _calls(("identity.create", {})),  # premature: must be refused
            _calls(("site.report_auth_methods", {"email_password": False, "methods": ["google"]})),
        ]
        _run(job, script, "https://example.com")
        assert job.state == "failed" and job.error_code == "AUTH_METHOD_UNSUPPORTED"
        assert job.identity_id is None  # nothing was created
        steps = list(job.steps.order_by("step_index"))
        assert steps[0].tool_result["success"] is False

    def test_user_ask_extends_the_deadline_and_job_continues(self, user, site, settings):
        settings.HUMAN_ASSIST_TIMEOUT_SECONDS = 30
        job = make_job(user, site, kind="form")
        script = [
            _calls(("user.ask", {"question": "Which county do you live in?", "field_key": "county"})),
            _calls(("form.complete", {"submitted": [{"question": "County", "answer": "Nairobi"}]})),
        ]
        with patch("apps.ai_agent.questions.time.sleep",
                   side_effect=lambda _: questions.record_answer(AgentQuestion.objects.get(), "Nairobi", remember=True)):
            provider = _run(job, script, "https://forms.gle/x")
        assert job.state == "completed"
        # The answer reached the model as the tool result.
        tool_msg = [m for m in provider.seen_messages[1] if m.role == "tool"][0]
        assert json.loads(tool_msg.content)["result"]["answer"] == "Nairobi"
        assert ProfileEntry.objects.get(user=user, key="county").get_value() == "Nairobi"
