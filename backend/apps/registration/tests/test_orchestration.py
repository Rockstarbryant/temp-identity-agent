from unittest.mock import MagicMock, patch

import pytest

from ai.base import AIProvider
from ai.schemas import ChatMessage, CompletionResult, ToolCallRequest
from apps.registration.models import DomainPolicy, RegistrationJob, TargetWebsite
from apps.registration.orchestration import start_registration_job

pytestmark = pytest.mark.django_db


class TestDomainPolicy:
    def test_blocked_domain_fails_immediately(self, user):
        site = TargetWebsite.objects.create(domain="blocked.com", registration_url="https://blocked.com/register")
        DomainPolicy.objects.create(domain="blocked.com", status="blocked", reason="Known abuse")
        job = RegistrationJob.objects.create(user=user, target_website=site)

        result = start_registration_job(job.id)
        assert result.state == "failed"
        assert result.error_code == "DOMAIN_BLOCKED"

    def test_requires_human_skips_agent(self, user):
        site = TargetWebsite.objects.create(domain="human.com", registration_url="https://human.com/register")
        DomainPolicy.objects.create(domain="human.com", status="requires_human")
        job = RegistrationJob.objects.create(user=user, target_website=site)

        result = start_registration_job(job.id)
        assert result.state == "human_action_required"

    def test_unlisted_domain_defaults_allowed(self, user):
        # No DomainPolicy row at all — should proceed to STARTING, not fail.
        site = TargetWebsite.objects.create(domain="unlisted.com", registration_url="https://unlisted.com/register")
        job = RegistrationJob.objects.create(user=user, target_website=site)

        with patch("apps.registration.orchestration.AgentRunner") as MockRunner:
            MockRunner.return_value.run.return_value = job
            start_registration_job(job.id)
        assert MockRunner.called  # agent was actually invoked


class TestRateLimits:
    def test_concurrent_job_limit_enforced(self, user, settings):
        settings.MAX_CONCURRENT_JOBS = 2
        site = TargetWebsite.objects.create(domain="open.com", registration_url="https://open.com/register")
        RegistrationJob.objects.create(user=user, target_website=site, state="analyzing")
        RegistrationJob.objects.create(user=user, target_website=site, state="filling_form")
        job = RegistrationJob.objects.create(user=user, target_website=site)

        result = start_registration_job(job.id)
        assert result.state == "failed"
        assert result.error_code == "RATE_LIMITED"

    def test_daily_quota_enforced(self, user, settings):
        settings.MAX_JOBS_PER_USER_PER_DAY = 1
        site = TargetWebsite.objects.create(domain="open.com", registration_url="https://open.com/register")
        RegistrationJob.objects.create(user=user, target_website=site, state="completed")
        job = RegistrationJob.objects.create(user=user, target_website=site)

        result = start_registration_job(job.id)
        assert result.state == "failed"
        assert result.error_code == "RATE_LIMITED"


class TestRegistrationJobAPI:
    def test_create_job_rejects_ssrf_url(self, auth_client):
        r = auth_client.post("/api/registration-jobs/", {"url": "http://169.254.169.254/"})
        assert r.status_code == 400

    def test_create_job_requires_auth(self, api_client):
        r = api_client.post("/api/registration-jobs/", {"url": "https://example.com/register"})
        assert r.status_code == 401

    def test_full_flow_via_api(self, auth_client):
        script = [
            CompletionResult(message=ChatMessage(role="assistant", content="", tool_calls=[
                ToolCallRequest(id="c1", name="identity.create", arguments={})])),
            CompletionResult(message=ChatMessage(role="assistant", content="", tool_calls=[
                ToolCallRequest(id="c2", name="registration.mark_complete", arguments={})])),
        ]

        class ScriptedProvider(AIProvider):
            name = "scripted"

            def __init__(self):
                self.script = list(script)

            def complete(self, messages, tools):
                return self.script.pop(0)

        class FakeSession:
            def __init__(self, job, headless=True):
                self.page = MagicMock()
                self.page.url = "https://example.com/register"
                self.page.title.return_value = "Register"
                self.page.evaluate.return_value = []

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def goto(self, url):
                self.page.url = url

        def fake_mailbox(identity):
            from apps.email_service.models import TemporaryEmail

            mb = TemporaryEmail(identity=identity, provider="mailtm", address="x@test.example", expires_at=identity.expires_at)
            mb.set_credential("jwt")
            mb.save()
            identity.email = mb.address
            identity.save(update_fields=["email"])
            return mb

        with patch("apps.ai_agent.agent_loop.ManagedBrowserSession", FakeSession), \
             patch("apps.ai_agent.agent_loop.get_ai_provider", return_value=ScriptedProvider()), \
             patch("apps.email_service.service.create_mailbox_for_identity", side_effect=fake_mailbox):
            r = auth_client.post("/api/registration-jobs/", {"url": "https://example.com/register"})

        assert r.status_code == 201
        assert r.json()["state"] == "completed"

        job_id = r.json()["id"]
        r = auth_client.get(f"/api/registration-jobs/{job_id}/")
        assert len(r.json()["steps"]) == 2

    def test_cross_user_job_access_denied(self, auth_client, other_auth_client, user):
        site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")
        job = RegistrationJob.objects.create(user=user, target_website=site)
        r = other_auth_client.get(f"/api/registration-jobs/{job.id}/")
        assert r.status_code == 404

    def test_cancel_terminal_job_rejected(self, auth_client, user):
        site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")
        job = RegistrationJob.objects.create(user=user, target_website=site, state="completed")
        r = auth_client.post(f"/api/registration-jobs/{job.id}/cancel/")
        assert r.status_code == 400

    def test_resume_non_resumable_job_rejected(self, auth_client, user):
        site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")
        job = RegistrationJob.objects.create(user=user, target_website=site, state="completed")
        r = auth_client.post(f"/api/registration-jobs/{job.id}/resume/")
        assert r.status_code == 400
