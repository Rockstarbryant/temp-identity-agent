import pytest
from django.contrib.admin.sites import site
from django.core.management import call_command

from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_skips_without_env(monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    call_command("ensure_admin")
    assert User.objects.count() == 0


def test_creates_then_updates_superuser(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "boss")
    monkeypatch.setenv("ADMIN_PASSWORD", "first-Password-1")
    call_command("ensure_admin")
    u = User.objects.get(username="boss")
    assert u.is_superuser and u.is_staff and u.check_password("first-Password-1")
    monkeypatch.setenv("ADMIN_PASSWORD", "second-Password-2")
    call_command("ensure_admin")
    assert User.objects.count() == 1
    assert User.objects.get(username="boss").check_password("second-Password-2")


def test_admin_hides_secrets_and_is_read_only(rf):
    from apps.profiles.models import ConnectedAccount
    from apps.mcp_server.models import ApiKey

    for model, secrets in ((ConnectedAccount, {"encrypted_password", "encrypted_session"}), (ApiKey, {"key_hash"})):
        ma = site._registry[model]
        req = rf.get("/")
        assert not ma.has_add_permission(req) and not ma.has_change_permission(req)
        assert secrets <= set(ma.get_exclude(req))
        assert not (secrets & set(ma.get_readonly_fields(req)))


def test_domain_policy_is_editable(rf, db):
    from apps.registration.models import DomainPolicy

    req = rf.get("/")
    req.user = User.objects.create_superuser("root2", "r2@example.com", "pw-Strong-123")
    assert site._registry[DomainPolicy].has_add_permission(req) is True


def test_admin_login_page_and_index(client):
    User.objects.create_superuser("root", "r@example.com", "pw-Strong-123")
    client.login(username="root", password="pw-Strong-123")
    assert client.get("/admin/").status_code == 200
    assert client.get("/admin/registration/domainpolicy/").status_code == 200
    assert client.get("/admin/registration/registrationjob/").status_code == 200
    assert client.get("/admin/profiles/connectedaccount/").status_code == 200
