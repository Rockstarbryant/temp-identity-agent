from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.accounts.models import TemporaryAccount
from apps.registration import manual
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


def el(tag="input", type="text", label="", name="", visible=True, **kw):
    return {"tag": tag, "type": type, "label": label, "name": name, "placeholder": "", "visible": visible,
            "options": [], "group": "", "required": False, **kw}


FORM = [
    el(label="Email address", type="email"), el(label="Password", type="password", required=True),
    el(label="First name"), el(label="Last name"), el(label="Phone number"), el(label="Referral code"),
    el(type="hidden", label="csrf"), el(tag="button", label="Sign up"), el(label="Email address", type="email"),
    el(tag="select", label="Country", options=["Kenya", "Peru"]), el(label="Hidden", visible=False),
]


def make_job(user, state="captcha_required"):
    site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")
    return RegistrationJob.objects.create(user=user, target_website=site, state=state)


def test_build_kit_maps_fields_and_skips_noise():
    kit = manual.build_kit(SimpleNamespace(elements=FORM))
    got = [(f["label"], f["source"]) for f in kit["fields"]]
    assert got == [("Email address", "email"), ("Password", "password"), ("First name", "first_name"),
                   ("Last name", "last_name"), ("Phone number", "profile:phone"), ("Referral code", ""),
                   ("Country", "profile:country")]
    assert "value" not in kit["fields"][0]  # descriptors only


def test_snapshot_into_job_is_best_effort(user, monkeypatch):
    job = make_job(user)
    ctx = SimpleNamespace(job=job, session=SimpleNamespace(page=MagicMock(url="https://example.com/register")))
    monkeypatch.setattr("apps.browser.page_inspector.inspect_page", lambda page: SimpleNamespace(elements=FORM))
    ctx.session.page.title.return_value = "Sign up"
    manual.snapshot_into_job(ctx)
    job.refresh_from_db()
    assert len(job.result["manual_kit"]["fields"]) == 7

    def boom(page):
        raise RuntimeError("page closed")

    monkeypatch.setattr("apps.browser.page_inspector.inspect_page", boom)
    manual.snapshot_into_job(ctx)  # must not raise


def test_captcha_handler_stores_the_kit(user, monkeypatch):
    from apps.ai_agent.context import AgentContext
    from apps.ai_agent.tools import _handle_registration_mark_captcha_required
    from apps.identities import service as identity_service

    job = make_job(user, "analyzing")
    ctx = AgentContext(job=job, identity=identity_service.create_temporary_identity(user))
    ctx.session = SimpleNamespace(page=MagicMock(url="https://example.com/register"))
    monkeypatch.setattr("apps.browser.page_inspector.inspect_page", lambda page: SimpleNamespace(elements=FORM))
    _handle_registration_mark_captcha_required(ctx, SimpleNamespace(reason="reCAPTCHA"))
    job.refresh_from_db()
    assert job.state == "captcha_required" and job.result["manual_kit"]["fields"]


@pytest.fixture
def no_mailbox(monkeypatch):
    def fake(identity):
        from apps.email_service.models import TemporaryEmail

        box = TemporaryEmail(identity=identity, provider="mailtm", address="x@test.example", expires_at=identity.expires_at)
        box.set_credential("jwt")
        box.save()
        return box

    monkeypatch.setattr("apps.email_service.service.create_mailbox_for_identity", fake)


def test_kit_endpoint_returns_values_and_creates_identity_if_missing(auth_client, user, no_mailbox):
    job = make_job(user)
    job.result = {"manual_kit": manual.build_kit(SimpleNamespace(elements=FORM))}
    job.save()
    r = auth_client.post(f"/api/registration-jobs/{job.id}/manual-kit/")
    assert r.status_code == 200
    job.refresh_from_db()
    fields = {f["label"]: f for f in r.data["fields"]}
    assert fields["Email address"]["value"] == job.identity.email
    assert fields["Password"]["value"] == job.identity.get_password() and fields["Password"]["secret"] is True
    assert r.data["password"] == job.identity.get_password()
    from apps.audit.models import AuditLog

    assert AuditLog.objects.filter(action="job.manual_kit_revealed").exists()


def test_kit_refused_for_wrong_state_and_other_users(auth_client, other_auth_client, user, no_mailbox):
    running = make_job(user, "analyzing")
    assert auth_client.post(f"/api/registration-jobs/{running.id}/manual-kit/").status_code == 400
    waiting = RegistrationJob.objects.create(user=user, target_website=running.target_website, state="captcha_required")
    assert other_auth_client.post(f"/api/registration-jobs/{waiting.id}/manual-kit/").status_code == 404


def test_manual_complete_saves_to_vault_with_edits(auth_client, user, no_mailbox):
    from apps.notifications.models import Notification

    job = make_job(user)
    r = auth_client.post(f"/api/registration-jobs/{job.id}/manual-complete/",
                         {"username": "kim_k", "password": "My-Own-Pass-123", "note": "used phone 2"}, format="json")
    assert r.status_code == 200
    job.refresh_from_db()
    assert job.state == "completed" and job.result["manual"] is True
    account = TemporaryAccount.objects.get(job=job)
    assert account.identity.username == "kim_k" and account.identity.get_password() == "My-Own-Pass-123"
    assert Notification.objects.filter(user=user, kind="manual_saved").count() == 1

    vault = auth_client.get("/api/accounts/")
    assert vault.data["results"][0]["manual"] is True if "results" in vault.data else vault.data[0]["manual"] is True
    assert auth_client.post(f"/api/registration-jobs/{job.id}/manual-complete/").status_code == 400  # already done


def test_job_flags_manual_available(auth_client, user):
    job = make_job(user)
    assert auth_client.get(f"/api/registration-jobs/{job.id}/").data["manual_available"] is True
