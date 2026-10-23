from datetime import timedelta

import pytest
from django.utils import timezone

from apps.identities.tasks import fail_stalled_registration_jobs
from apps.registration.models import RegistrationJob, TargetWebsite


@pytest.fixture
def site():
    return TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")


def _job(user, site, state, age_minutes):
    job = RegistrationJob.objects.create(user=user, target_website=site, state=state)
    RegistrationJob.objects.filter(id=job.id).update(updated_at=timezone.now() - timedelta(minutes=age_minutes))
    return job


@pytest.mark.django_db
def test_stalled_running_job_is_failed(user, site):
    job = _job(user, site, "starting", 30)
    assert fail_stalled_registration_jobs() == 1
    job.refresh_from_db()
    assert job.state == "failed" and job.error_code == "WORKER_LOST" and job.completed_at


@pytest.mark.django_db
def test_recent_waiting_and_finished_jobs_are_left_alone(user, site):
    recent = _job(user, site, "starting", 1)
    waiting = _job(user, site, "waiting_for_user", 300)
    done = _job(user, site, "completed", 300)
    assert fail_stalled_registration_jobs() == 0
    for j, s in ((recent, "starting"), (waiting, "waiting_for_user"), (done, "completed")):
        j.refresh_from_db()
        assert j.state == s


@pytest.mark.django_db
def test_fail_unless_finished_survives_a_database_blip(user, site, monkeypatch):
    from django.db import OperationalError

    from apps.registration import orchestration

    job = _job(user, site, "starting", 0)
    class _Conn:  # closing the real connection would end the test's own transaction
        in_atomic_block = True
        connection = None
        def close(self): pass
    monkeypatch.setattr("apps.common.db.connection", _Conn())
    calls = {"n": 0}
    real = RegistrationJob.refresh_from_db

    def flaky(self, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("name resolution")
        return real(self, *a, **k)

    monkeypatch.setattr(RegistrationJob, "refresh_from_db", flaky)
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    orchestration._fail_unless_finished(job, "AI_ERROR", "x")
    job.refresh_from_db()
    assert job.state == "failed" and calls["n"] >= 2


def test_daily_limit_makes_fallback_skip_primary():
    from ai.base import AIProviderError
    from ai.providers import fallback as fb
    from ai.schemas import ChatMessage, CompletionResult

    class P:
        name, model = "p", "m"
        def __init__(self, fail): self.fail, self.calls = fail, 0
        def complete(self, m, t):
            self.calls += 1
            if self.fail:
                raise AIProviderError("429 free-models-per-day", retryable=True)
            return CompletionResult(message=ChatMessage(role="assistant", content="ok"), provider="g", model="m")

    f = fb.FallbackAIProvider.__new__(fb.FallbackAIProvider)
    f.primary, f.fallback, f.name, f.model = P(True), P(False), "p", "m"
    fb._primary_skip_until = 0.0
    f.complete([], []); f.complete([], [])
    assert f.primary.calls == 1 and f.fallback.calls == 2
    fb._primary_skip_until = 0.0
