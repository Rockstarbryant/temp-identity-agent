from unittest.mock import patch

import pytest

from apps.profiles.models import EmailConnection, ProfileEntry, UserPreferences
from apps.registration.jobs import is_google_form_url
from apps.registration.models import AgentQuestion, RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_dns_no_worker():
    with patch("apps.common.url_safety.validate_url", side_effect=lambda u: u), \
         patch("apps.registration.tasks.run_registration_job_task.delay") as delay:
        yield delay


def create(client, url):
    return client.post("/api/registration-jobs/", {"url": url}, format="json")


class TestFormDetection:
    @pytest.mark.parametrize("url,expected", [
        ("https://docs.google.com/forms/d/e/abc/viewform", True),
        ("https://forms.gle/abc123", True),
        ("https://forms.cloud.microsoft/pages/responsepage.aspx?id=abc", True),
        ("https://forms.office.com/r/abc", True),
        ("https://acme.typeform.com/to/abc", True),
        ("https://tally.so/r/abc", True),
        ("https://airtable.com/shrXYZ", True),
        ("https://docs.google.com/document/d/abc", False),
        ("https://example.com/forms/x", False),
    ])
    def test_is_google_form(self, url, expected):
        assert is_google_form_url(url) is expected

    def test_form_url_creates_form_job_with_its_own_url(self, auth_client):
        r1 = create(auth_client, "https://docs.google.com/forms/d/e/AAA/viewform")
        r2 = create(auth_client, "https://docs.google.com/forms/d/e/BBB/viewform")
        assert r1.status_code == r2.status_code == 201
        assert r1.json()["kind"] == "form"
        j1, j2 = RegistrationJob.objects.get(id=r1.json()["id"]), RegistrationJob.objects.get(id=r2.json()["id"])
        assert j1.target_url.endswith("AAA/viewform") and j2.target_url.endswith("BBB/viewform")
        assert j1.target_website_id == j2.target_website_id  # same domain, different forms

    def test_regular_site_is_a_registration_job(self, auth_client):
        assert create(auth_client, "https://example.com/register").json()["kind"] == "registration"


class TestAccountModeAtCreation:
    def test_permanent_without_email_is_refused(self, auth_client, user):
        UserPreferences.for_user(user).account_mode = "permanent"
        UserPreferences.objects.filter(user=user).update(account_mode="permanent")
        r = create(auth_client, "https://example.com/register")
        assert r.status_code == 400 and "Connect it in Settings" in r.json()["detail"]
        assert not RegistrationJob.objects.exists()

    def test_permanent_with_email_snapshots_mode(self, auth_client, user):
        UserPreferences.objects.update_or_create(user=user, defaults={"account_mode": "permanent"})
        c = EmailConnection(user=user, kind="imap", address="a@b.com", imap_host="h")
        c.set_secret("x")
        c.save()
        r = create(auth_client, "https://example.com/register")
        assert r.status_code == 201 and r.json()["account_mode"] == "permanent"
        UserPreferences.objects.filter(user=user).update(account_mode="temporary")
        assert RegistrationJob.objects.get().account_mode == "permanent"  # later changes don't affect it

    def test_forms_are_always_temporary_kind(self, auth_client, user):
        UserPreferences.objects.update_or_create(user=user, defaults={"account_mode": "permanent"})
        r = create(auth_client, "https://forms.gle/abc")
        assert r.status_code == 201 and r.json()["account_mode"] == "temporary"


class TestQuestionsApi:
    @pytest.fixture
    def waiting(self, user):
        site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com")
        job = RegistrationJob.objects.create(user=user, target_website=site, state="waiting_for_user")
        q = AgentQuestion.objects.create(job=job, key="home_county", question="Which county?", options=["Nairobi", "Kisumu"])
        return job, q

    def test_pending_question_in_job_detail(self, auth_client, waiting):
        job, q = waiting
        body = auth_client.get(f"/api/registration-jobs/{job.id}/").json()
        assert body["pending_question"]["question"] == "Which county?"
        assert body["pending_question"]["options"] == ["Nairobi", "Kisumu"]
        assert "answer" not in str(body["pending_question"]).lower().replace("question", "")

    def test_answer_and_remember(self, auth_client, user, waiting):
        job, q = waiting
        r = auth_client.post(f"/api/registration-jobs/{job.id}/questions/{q.id}/answer/",
                             {"answer": "Nairobi", "remember": True}, format="json")
        assert r.status_code == 202
        q.refresh_from_db()
        assert q.status == "answered" and q.get_answer() == "Nairobi"
        assert ProfileEntry.objects.get(user=user, key="home_county").get_value() == "Nairobi"
        assert auth_client.get(f"/api/registration-jobs/{job.id}/").json()["pending_question"] is None

    def test_answer_without_remember_is_not_saved(self, auth_client, user, waiting):
        job, q = waiting
        auth_client.post(f"/api/registration-jobs/{job.id}/questions/{q.id}/answer/", {"answer": "Kisumu"}, format="json")
        assert not ProfileEntry.objects.filter(user=user).exists()

    def test_skip(self, auth_client, waiting):
        job, q = waiting
        assert auth_client.post(f"/api/registration-jobs/{job.id}/questions/{q.id}/answer/", {"skip": True}, format="json").status_code == 202
        q.refresh_from_db()
        assert q.status == "skipped"

    def test_empty_answer_rejected_and_double_answer_conflicts(self, auth_client, waiting):
        job, q = waiting
        url = f"/api/registration-jobs/{job.id}/questions/{q.id}/answer/"
        assert auth_client.post(url, {"answer": "  "}, format="json").status_code == 400
        assert auth_client.post(url, {"answer": "Nairobi"}, format="json").status_code == 202
        assert auth_client.post(url, {"answer": "Again"}, format="json").status_code == 409

    def test_other_users_cannot_answer(self, api_client, other_user, waiting):
        from rest_framework_simplejwt.tokens import RefreshToken

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other_user).access_token}")
        job, q = waiting
        r = api_client.post(f"/api/registration-jobs/{job.id}/questions/{q.id}/answer/", {"answer": "x"}, format="json")
        assert r.status_code == 404

    def test_waiting_for_user_counts_as_active(self, auth_client, waiting):
        job, _ = waiting
        assert auth_client.delete(f"/api/registration-jobs/{job.id}/").status_code == 400


class TestRetryKeepsJobShape:
    def test_retry_copies_kind_url_goal_mode(self, auth_client, user):
        site = TargetWebsite.objects.create(domain="docs.google.com", registration_url="https://docs.google.com/forms/d/e/FIRST/viewform")
        old = RegistrationJob.objects.create(
            user=user, target_website=site, state="failed", kind="form", source="web",
            target_url="https://docs.google.com/forms/d/e/SECOND/viewform", goal="g",
        )
        r = auth_client.post(f"/api/registration-jobs/{old.id}/retry/")
        assert r.status_code == 201
        new = RegistrationJob.objects.get(id=r.json()["id"])
        assert new.kind == "form" and new.target_url.endswith("SECOND/viewform") and new.goal == "g"


class TestJobBudgets:
    def test_new_jobs_use_env_budgets(self, auth_client, settings):
        settings.MAX_AGENT_STEPS = 75
        settings.MAX_JOB_DURATION_SECONDS = 900
        r = create(auth_client, "https://example.com/register")
        from apps.registration.models import RegistrationJob

        job = RegistrationJob.objects.get(id=r.json()["id"])
        assert job.max_steps == 75 and job.timeout_seconds == 900
