import pytest

from apps.accounts.models import TemporaryAccount
from apps.identities.service import create_temporary_identity
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture
def completed_account(user):
    site = TargetWebsite.objects.create(domain="example.com", registration_url="https://example.com/register")
    identity = create_temporary_identity(user)
    job = RegistrationJob.objects.create(user=user, target_website=site, identity=identity, state="completed")
    return TemporaryAccount.objects.create(job=job, identity=identity, website=site)


class TestVaultList:
    def test_list_scoped_to_owner(self, auth_client, other_auth_client, completed_account):
        assert len(auth_client.get("/api/accounts/").json()["results"]) == 1
        assert len(other_auth_client.get("/api/accounts/").json()["results"]) == 0

    def test_list_never_includes_password(self, auth_client, completed_account):
        r = auth_client.get("/api/accounts/")
        assert "password" not in r.json()["results"][0]


class TestRevealCredentials:
    def test_reveal_returns_real_password(self, auth_client, completed_account):
        r = auth_client.post(f"/api/accounts/{completed_account.id}/reveal-credentials/")
        assert r.status_code == 200
        assert len(r.json()["password"]) == 20

    def test_reveal_is_audit_logged(self, auth_client, completed_account, user):
        auth_client.post(f"/api/accounts/{completed_account.id}/reveal-credentials/")
        from apps.audit.models import AuditLog

        assert AuditLog.objects.filter(
            user=user, action="account.credentials_revealed", resource_id=str(completed_account.id)
        ).exists()

    def test_cross_user_reveal_denied(self, other_auth_client, completed_account):
        r = other_auth_client.post(f"/api/accounts/{completed_account.id}/reveal-credentials/")
        assert r.status_code == 404

    def test_reveal_after_delete_returns_410(self, auth_client, completed_account):
        auth_client.delete(f"/api/accounts/{completed_account.id}/")
        r = auth_client.post(f"/api/accounts/{completed_account.id}/reveal-credentials/")
        assert r.status_code == 410


class TestDeleteAccount:
    def test_delete_scrubs_password_not_just_flags_status(self, auth_client, completed_account):
        r = auth_client.delete(f"/api/accounts/{completed_account.id}/")
        assert r.status_code == 204

        completed_account.refresh_from_db()
        completed_account.identity.refresh_from_db()
        assert completed_account.status == "deleted"
        assert completed_account.identity.encrypted_password == ""

    def test_cross_user_delete_denied(self, other_auth_client, completed_account):
        r = other_auth_client.delete(f"/api/accounts/{completed_account.id}/")
        assert r.status_code == 404
        completed_account.refresh_from_db()
        assert completed_account.status == "active"  # unchanged
