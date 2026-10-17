from unittest.mock import patch

import pytest

from apps.ai_agent.models import AgentSession
from apps.registration.models import RegistrationJob, RegistrationStep, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture
def site():
    return TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")


def _job(user, site, state):
    return RegistrationJob.objects.create(user=user, target_website=site, state=state)


class TestRetry:
    def test_retry_failed_job_creates_new_job_and_enqueues(self, auth_client, user, site):
        old = _job(user, site, "failed")
        with patch("apps.registration.views.run_registration_job_task.delay") as delay:
            r = auth_client.post(f"/api/registration-jobs/{old.id}/retry/")
        assert r.status_code == 201
        new_id = r.json()["id"]
        assert new_id != str(old.id)
        delay.assert_called_once_with(new_id)
        assert RegistrationJob.objects.get(id=new_id).target_website_id == site.id
        old.refresh_from_db()
        assert old.state == "failed"  # original untouched

    @pytest.mark.parametrize("state", ["completed", "queued", "starting", "captcha_required"])
    def test_retry_rejected_for_other_states(self, auth_client, user, site, state):
        job = _job(user, site, state)
        with patch("apps.registration.views.run_registration_job_task.delay") as delay:
            r = auth_client.post(f"/api/registration-jobs/{job.id}/retry/")
        assert r.status_code == 400
        delay.assert_not_called()

    def test_cannot_retry_someone_elses_job(self, other_auth_client, user, site):
        job = _job(user, site, "failed")
        r = other_auth_client.post(f"/api/registration-jobs/{job.id}/retry/")
        assert r.status_code == 404


class TestDelete:
    def test_delete_hides_finished_job(self, auth_client, user, site):
        job = _job(user, site, "failed")
        assert auth_client.delete(f"/api/registration-jobs/{job.id}/").status_code == 204
        ids = [j["id"] for j in auth_client.get("/api/registration-jobs/").json()["results"]]
        assert str(job.id) not in ids
        assert auth_client.get(f"/api/registration-jobs/{job.id}/").status_code == 404
        assert RegistrationJob.objects.filter(id=job.id).exists()  # soft delete

    def test_running_job_cannot_be_deleted(self, auth_client, user, site):
        job = _job(user, site, "starting")
        r = auth_client.delete(f"/api/registration-jobs/{job.id}/")
        assert r.status_code == 400
        job.refresh_from_db()
        assert job.dismissed_at is None

    def test_paused_job_can_be_deleted(self, auth_client, user, site):
        job = _job(user, site, "captcha_required")
        assert auth_client.delete(f"/api/registration-jobs/{job.id}/").status_code == 204

    def test_deleting_completed_job_keeps_vault_account(self, auth_client, user, site):
        from apps.accounts.models import TemporaryAccount
        from apps.identities import service as identity_service

        job = _job(user, site, "completed")
        identity = identity_service.create_temporary_identity(user)
        account = TemporaryAccount.objects.create(job=job, identity=identity, website=site)
        assert auth_client.delete(f"/api/registration-jobs/{job.id}/").status_code == 204
        assert TemporaryAccount.objects.filter(id=account.id, status="active").exists()

    def test_clear_finished_only_hides_failed_cancelled_expired(self, auth_client, user, site):
        failed = _job(user, site, "failed")
        cancelled = _job(user, site, "cancelled")
        completed = _job(user, site, "completed")
        paused = _job(user, site, "captcha_required")
        r = auth_client.post("/api/registration-jobs/clear-finished/")
        assert r.json() == {"cleared": 2}
        visible = {j["id"] for j in auth_client.get("/api/registration-jobs/").json()["results"]}
        assert visible == {str(completed.id), str(paused.id)}
        assert str(failed.id) not in visible and str(cancelled.id) not in visible


class TestSerializerExposure:
    def test_job_exposes_provider_model_and_account(self, auth_client, user, site):
        from apps.accounts.models import TemporaryAccount
        from apps.identities import service as identity_service

        job = _job(user, site, "completed")
        AgentSession.objects.create(job=job, provider="groq", model="llama-3.3-70b-versatile")
        identity = identity_service.create_temporary_identity(user)
        account = TemporaryAccount.objects.create(job=job, identity=identity, website=site)
        data = auth_client.get(f"/api/registration-jobs/{job.id}/").json()
        assert data["provider"] == "groq"
        assert data["model"] == "llama-3.3-70b-versatile"
        assert data["account_id"] == str(account.id)

    def test_job_without_session_or_account_has_blanks(self, auth_client, user, site):
        job = _job(user, site, "queued")
        data = auth_client.get(f"/api/registration-jobs/{job.id}/").json()
        assert data["provider"] == "" and data["model"] == "" and data["account_id"] is None

    def test_steps_expose_detail_not_raw_tool_data(self, auth_client, user, site):
        job = _job(user, site, "failed")
        RegistrationStep.objects.create(
            job=job, step_index=0, action="browser.click", tool_name="browser.click",
            tool_input={"element_id": "e3"}, tool_result={"success": True, "result": {"snapshot": {"x": 1}}},
            detail="Clicked the “Sign up” button",
        )
        step = auth_client.get(f"/api/registration-jobs/{job.id}/").json()["steps"][0]
        assert step["detail"] == "Clicked the “Sign up” button"
        assert step["success"] is True
        assert "tool_result" not in step and "tool_input" not in step
