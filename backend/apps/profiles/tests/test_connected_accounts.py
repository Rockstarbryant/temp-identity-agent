import json
from unittest.mock import MagicMock, patch

import pytest

from ai.schemas import ToolCallRequest
from apps.ai_agent.context import AgentContext
from apps.ai_agent.dispatcher import dispatch_tool_call
from apps.profiles import signin
from apps.profiles.models import ConnectedAccount
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db

URL = "/api/connected-accounts/"


@pytest.fixture
def site():
    return TargetWebsite.objects.create(domain="docs.google.com", registration_url="https://docs.google.com/forms/d/e/X/viewform")


def form_job(user, site):
    return RegistrationJob.objects.create(
        user=user, target_website=site, kind="form", state="analyzing",
        target_url="https://docs.google.com/forms/d/e/X/viewform",
    )


def make_account(user, provider="google", password="pw-1", session=None):
    a = ConnectedAccount(user=user, provider=provider, email=f"agent@{provider}.test")
    a.set_password(password)
    if session:
        a.set_session(session)
    a.save()
    return a


class TestHelpers:
    def test_provider_for_url(self):
        assert signin.provider_for_url("https://docs.google.com/forms/d/e/X/viewform") == "google"
        assert signin.provider_for_url("https://forms.gle/abc") == "google"
        assert signin.provider_for_url("https://forms.cloud.microsoft/pages/responsepage.aspx") == "microsoft"
        assert signin.provider_for_url("https://forms.office.com/r/abc") == "microsoft"
        assert signin.provider_for_url("https://example.com/") == ""

    def test_is_login_url(self):
        assert signin.is_login_url("google", "https://accounts.google.com/v3/signin/identifier")
        assert signin.is_login_url("microsoft", "https://login.microsoftonline.com/common/oauth2")
        assert not signin.is_login_url("google", "https://docs.google.com/forms/d/e/X/viewform")


class TestModel:
    def test_secrets_are_encrypted_and_round_trip(self, user):
        a = make_account(user, session={"cookies": [{"name": "SID", "value": "secret-cookie"}], "origins": []})
        a.refresh_from_db()
        assert "pw-1" not in a.encrypted_password and "secret-cookie" not in a.encrypted_session
        assert a.get_password() == "pw-1"
        assert a.get_session()["cookies"][0]["value"] == "secret-cookie"
        assert a.has_password and a.has_session

    def test_corrupt_session_is_just_signed_out(self, user):
        a = make_account(user)
        a.encrypted_session = "garbage"
        assert a.get_session() is None


class TestApi:
    def test_save_list_never_returns_secrets(self, auth_client):
        r = auth_client.put(URL, {"provider": "google", "email": "Agent@Gmail.com", "password": "hunter2"}, format="json")
        assert r.status_code == 200 and r.json()["email"] == "agent@gmail.com" and r.json()["has_password"] is True
        body = auth_client.get(URL).content.decode()
        assert "hunter2" not in body and "encrypted" not in body

    def test_blank_password_keeps_saved_one(self, auth_client, user):
        auth_client.put(URL, {"provider": "google", "email": "a@gmail.com", "password": "keep-me"}, format="json")
        auth_client.put(URL, {"provider": "google", "email": "a@gmail.com", "password": ""}, format="json")
        assert ConnectedAccount.objects.get(user=user).get_password() == "keep-me"

    def test_changing_email_drops_old_session_and_password(self, auth_client, user):
        make_account(user, session={"cookies": [{"name": "a"}]})
        r = auth_client.put(URL, {"provider": "google", "email": "other@gmail.com"}, format="json")
        assert r.json()["signed_in"] is False and r.json()["has_password"] is False

    def test_validation(self, auth_client):
        assert auth_client.put(URL, {"provider": "yahoo", "email": "a@b.com"}, format="json").status_code == 400
        assert auth_client.put(URL, {"provider": "google", "email": "nope"}, format="json").status_code == 400

    def test_accounts_are_per_user(self, auth_client, other_user, user):
        make_account(other_user)
        assert auth_client.get(URL).json() == []
        assert auth_client.delete(f"{URL}google/").status_code == 204
        assert ConnectedAccount.objects.filter(user=other_user).exists()  # not touched

    def test_delete_erases(self, auth_client, user):
        make_account(user)
        auth_client.delete(f"{URL}google/")
        assert not ConnectedAccount.objects.exists()

    def test_signin_creates_setup_job(self, auth_client, user):
        make_account(user)
        with patch("apps.registration.jobs.run_registration_job_task.delay") as delay:
            r = auth_client.post(f"{URL}google/signin/")
        assert r.status_code == 201 and r.json()["kind"] == "account_setup"
        job = RegistrationJob.objects.get(id=r.json()["id"])
        assert job.goal == "google" and job.user == user
        delay.assert_called_once()

    def test_signin_requires_account(self, auth_client):
        assert auth_client.post(f"{URL}google/signin/").status_code == 400


def call(ctx, name="account.sign_in", **args):
    return dispatch_tool_call(ctx, ToolCallRequest(id="1", name=name, arguments=args))


def ctx_for(job, url):
    session = MagicMock()
    session.page.url = url
    return AgentContext(job=job, session=session)


class TestSignInTool:
    def test_not_on_login_page_does_nothing(self, user, site):
        ctx = ctx_for(form_job(user, site), "https://docs.google.com/forms/d/e/X/viewform")
        out = call(ctx)
        assert out["success"] and out["result"]["signed_in"] is True

    def test_not_a_supported_site(self, user, site):
        job = form_job(user, site)
        job.target_url = "https://example.com/form"
        ctx = ctx_for(job, "https://example.com/form")
        assert call(ctx)["result"]["success"] is False

    def test_no_connected_account_pauses_for_the_user(self, user, site):
        job = form_job(user, site)
        out = call(ctx_for(job, "https://accounts.google.com/v3/signin/identifier"))
        job.refresh_from_db()
        assert job.state == "human_action_required" and "Sign in" in job.error_message
        assert out["result"]["paused_for_human"] is True

    def test_successful_login_saves_session_and_never_exposes_password(self, user, site):
        account = make_account(user, password="very-secret-pw")
        job = form_job(user, site)
        ctx = ctx_for(job, "https://accounts.google.com/v3/signin/identifier")
        ctx.session.export_storage_state.return_value = {"cookies": [{"name": "SID", "value": "x"}], "origins": []}
        with patch("apps.profiles.signin.perform_login", return_value=signin.LoginResult(True)):
            out = call(ctx)
        assert "very-secret-pw" not in json.dumps(out)
        assert ctx.signed_in is True
        account.refresh_from_db()
        assert account.has_session and account.session_saved_at

    def test_challenge_hands_over_to_user(self, user, site):
        make_account(user)
        job = form_job(user, site)
        ctx = ctx_for(job, "https://accounts.google.com/v3/signin/challenge")
        with patch("apps.profiles.signin.perform_login", return_value=signin.LoginResult(False, True, "Google needs an extra check")):
            call(ctx)
        job.refresh_from_db()
        assert job.state == "human_action_required" and job.error_message == "Google needs an extra check"
        assert ctx.awaiting_signin is True and ctx.signed_in is False
        assert ConnectedAccount.objects.get(user=user).last_error == "Google needs an extra check"


class TestSessionIsolation:
    def test_runner_loads_only_the_owners_session(self, user, other_user, site):
        from apps.ai_agent.tests.test_ask_and_modes import _calls, _run

        make_account(other_user, session={"cookies": [{"name": "SID", "value": "bobs-cookie"}], "origins": []})
        make_account(user, session={"cookies": [{"name": "SID", "value": "alices-cookie"}], "origins": []})
        job = form_job(user, site)
        seen = {}

        class Session:
            def __init__(self, job, headless=True, storage_state=None):
                seen["state"] = storage_state
                self.page = MagicMock()
                self.page.url = "https://docs.google.com/forms/d/e/X/viewform"
                self.page.title.return_value = "F"
                self.page.evaluate.return_value = []

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        from apps.ai_agent.tests.test_ask_and_modes import _Scripted

        script = [_calls(("form.complete", {"submitted": [{"question": "q", "answer": "a"}]}))]
        from apps.ai_agent.agent_loop import AgentRunner

        with patch("apps.ai_agent.agent_loop.ManagedBrowserSession", Session), \
             patch("apps.ai_agent.agent_loop.get_ai_provider", return_value=_Scripted(script)):
            AgentRunner(job).run(job.target_url)
        assert seen["state"]["cookies"][0]["value"] == "alices-cookie"

    def test_no_account_means_clean_browser(self, user, other_user, site):
        from apps.ai_agent.agent_loop import AgentRunner
        from apps.ai_agent.tests.test_ask_and_modes import _Scripted, _calls

        make_account(other_user, session={"cookies": [{"name": "SID", "value": "bobs-cookie"}], "origins": []})
        job = form_job(user, site)
        seen = {}

        class Session:
            def __init__(self, job, headless=True, storage_state=None):
                seen["state"] = storage_state
                self.page = MagicMock()
                self.page.url = job.target_url
                self.page.title.return_value = "F"
                self.page.evaluate.return_value = []

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        script = [_calls(("form.complete", {"submitted": [{"question": "q", "answer": "a"}]}))]
        with patch("apps.ai_agent.agent_loop.ManagedBrowserSession", Session), \
             patch("apps.ai_agent.agent_loop.get_ai_provider", return_value=_Scripted(script)):
            AgentRunner(job).run(job.target_url)
        assert seen["state"] is None


class TestAccountSetupJob:
    def _job(self, user):
        site = TargetWebsite.objects.create(domain="accounts.google.com", registration_url="https://accounts.google.com/ServiceLogin")
        return RegistrationJob.objects.create(
            user=user, target_website=site, kind="account_setup", goal="google", state="starting",
            target_url="https://accounts.google.com/ServiceLogin",
        )

    def _session(self, final_url):
        s = MagicMock()
        s.__enter__.return_value = s
        s.__exit__.return_value = False
        s.page.url = final_url
        s.export_storage_state.return_value = {"cookies": [{"name": "SID", "value": "x"}], "origins": []}
        return s

    def test_password_login_saves_session(self, user):
        from apps.ai_agent.account_setup import run_account_setup

        account = make_account(user)
        job = self._job(user)
        with patch("apps.ai_agent.account_setup.ManagedBrowserSession", return_value=self._session("https://myaccount.google.com/")), \
             patch("apps.profiles.signin.perform_login", return_value=signin.LoginResult(True)):
            run_account_setup(job)
        job.refresh_from_db()
        account.refresh_from_db()
        assert job.state == "completed" and account.has_session

    def test_challenge_waits_for_user_then_saves(self, user):
        from apps.ai_agent.account_setup import run_account_setup

        account = make_account(user, password="")
        job = self._job(user)

        def fake_hold(j, session, frames):
            j.state = "analyzing"
            j.save(update_fields=["state"])
            return True

        with patch("apps.ai_agent.account_setup.ManagedBrowserSession", return_value=self._session("https://myaccount.google.com/")), \
             patch("apps.profiles.signin.perform_login", return_value=signin.LoginResult(False, True, "Enter your Google password")), \
             patch("apps.ai_agent.account_setup.hold_for_human", side_effect=fake_hold):
            run_account_setup(job)
        job.refresh_from_db()
        account.refresh_from_db()
        assert job.state == "completed" and account.has_session

    def test_user_not_actually_signed_in_fails(self, user):
        from apps.ai_agent.account_setup import run_account_setup

        make_account(user)
        job = self._job(user)
        with patch("apps.ai_agent.account_setup.ManagedBrowserSession", return_value=self._session("https://accounts.google.com/v3/signin")), \
             patch("apps.profiles.signin.perform_login", return_value=signin.LoginResult(False, True, "x")), \
             patch("apps.ai_agent.account_setup.hold_for_human", return_value=True):
            run_account_setup(job)
        job.refresh_from_db()
        assert job.state == "failed" and "not signed in" in job.error_message

    def test_dispatched_from_orchestration(self, user):
        from apps.registration.orchestration import start_registration_job

        make_account(user)
        job = self._job(user)
        job.state = "queued"
        job.save()
        with patch("apps.ai_agent.account_setup.run_account_setup") as run:
            start_registration_job(job.id)
        run.assert_called_once()


class TestRealChromiumLogin:
    """Drives the real login helpers against a fake Google page in Chromium (skipped if none)."""

    LOGIN = """<html><body><input type="email" id="e">
    <script>
    document.getElementById('e').addEventListener('keydown', ev => { if (ev.key === 'Enter') {
      document.body.innerHTML = '<input type="password" id="p">';
      document.getElementById('p').addEventListener('keydown', e2 => { if (e2.key === 'Enter') {
        if (document.getElementById('p').value === 'good') location.href = 'https://myaccount.google.com/';
        else document.body.insertAdjacentHTML('beforeend', '<p>Wrong password</p>'); } });
    }});</script></body></html>"""

    def _run(self, password):
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        try:
            try:
                browser = pw.chromium.launch()
            except Exception as exc:  # noqa: BLE001
                pytest.skip(f"No usable Chromium here: {exc}")
            ctx = browser.new_context()
            page = ctx.new_page()

            def handle(route):
                if "accounts.google.com" in route.request.url:
                    route.fulfill(status=200, content_type="text/html", body=self.LOGIN)
                else:
                    route.fulfill(status=200, content_type="text/html", body="<html>signed in</html>")

            ctx.route("**/*", handle)
            page.goto("https://accounts.google.com/ServiceLogin")
            account = ConnectedAccount(provider="google", email="a@gmail.com")
            account.set_password(password)
            result = signin._google_login(page, "a@gmail.com", password)
            return result, page.url, ctx.storage_state()
        finally:
            pw.stop()

    def test_good_password_signs_in(self):
        result, url, _ = self._run("good")
        assert result.ok and "myaccount.google.com" in url

    def test_wrong_password_hands_over(self):
        with patch.object(signin, "_left_login", wraps=lambda page, provider, ms: signin.is_login_url(provider, page.url) is False and False):
            result, url, _ = self._run("bad")
        assert not result.ok and result.needs_human and "wrong" in result.reason.lower()
