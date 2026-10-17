from unittest.mock import MagicMock, patch

import pytest
from django.core import signing

from apps.email_service.providers.base import EmailProviderError
from apps.profiles.models import EmailConnection, ProfileEntry, UserPreferences

pytestmark = pytest.mark.django_db


class TestPreferencesAndProfile:
    def test_default_mode_is_temporary(self, auth_client):
        body = auth_client.get("/api/profile/").json()
        assert body["account_mode"] == "temporary" and body["entries"] == []
        assert any(f["key"] == "phone" for f in body["standard_fields"])

    def test_switch_mode(self, auth_client, user):
        assert auth_client.patch("/api/preferences/", {"account_mode": "permanent"}, format="json").status_code == 200
        assert UserPreferences.for_user(user).account_mode == "permanent"
        assert auth_client.patch("/api/preferences/", {"account_mode": "nope"}, format="json").status_code == 400

    def test_save_update_and_delete_entry(self, auth_client, user):
        r = auth_client.put("/api/profile/entries/phone/", {"value": "0712345678"}, format="json")
        assert r.status_code == 200 and r.json()["label"] == "Phone number"
        entry = ProfileEntry.objects.get(user=user, key="phone")
        assert "0712345678" not in entry.encrypted_value  # encrypted at rest
        auth_client.put("/api/profile/entries/phone/", {"value": "0799999999"}, format="json")
        assert ProfileEntry.objects.filter(user=user, key="phone").count() == 1
        assert auth_client.get("/api/profile/").json()["entries"][0]["value"] == "0799999999"
        assert auth_client.put("/api/profile/entries/phone/", {"value": ""}, format="json").status_code == 204
        assert not ProfileEntry.objects.filter(user=user).exists()

    def test_custom_key_is_normalized(self, auth_client, user):
        auth_client.put("/api/profile/entries/Home%20County/", {"value": "Nairobi", "label": "Home county"}, format="json")
        assert ProfileEntry.objects.get(user=user).key == "home_county"

    @pytest.mark.parametrize("key", ["password", "card_number", "my_secret_word"])
    def test_secrets_are_refused(self, auth_client, key):
        assert auth_client.put(f"/api/profile/entries/{key}/", {"value": "x"}, format="json").status_code == 400

    def test_entries_are_private_to_the_user(self, auth_client, other_user):
        ProfileEntry.save_value(other_user, "phone", "0700000000")
        assert auth_client.get("/api/profile/").json()["entries"] == []

    def test_requires_login(self, api_client):
        assert api_client.get("/api/profile/").status_code == 401


class TestEmailConnection:
    def test_connect_imap_verifies_then_saves_encrypted(self, auth_client, user):
        imap = MagicMock()
        with patch("apps.profiles.views.validate_url"), patch("apps.profiles.views.open_imap", return_value=imap) as op:
            r = auth_client.put("/api/email-connection/", {"address": "Me@Gmail.com", "password": "abcd efgh"}, format="json")
        assert r.status_code == 200
        op.assert_called_once_with("imap.gmail.com", 993, "me@gmail.com", "abcd efgh")
        body = r.json()
        assert body["connected"] and body["kind"] == "imap" and "password" not in str(body)
        conn = EmailConnection.objects.get(user=user)
        assert "abcd" not in conn.encrypted_secret and conn.get_secret() == "abcd efgh"

    def test_bad_login_is_reported_and_not_saved(self, auth_client, user):
        with patch("apps.profiles.views.validate_url"), \
             patch("apps.profiles.views.open_imap", side_effect=EmailProviderError("rejected")):
            r = auth_client.put("/api/email-connection/", {"address": "me@gmail.com", "password": "x"}, format="json")
        assert r.status_code == 400 and "rejected" in r.json()["detail"]
        assert not EmailConnection.objects.filter(user=user).exists()

    def test_unknown_provider_needs_host(self, auth_client):
        r = auth_client.put("/api/email-connection/", {"address": "me@mydomain.org", "password": "x"}, format="json")
        assert r.status_code == 400 and "IMAP host" in r.json()["detail"]

    def test_internal_host_is_refused(self, auth_client):
        r = auth_client.put("/api/email-connection/",
                            {"address": "me@mydomain.org", "password": "x", "host": "169.254.169.254"}, format="json")
        assert r.status_code == 400 and "isn't allowed" in r.json()["detail"]

    def test_get_and_disconnect(self, auth_client, user):
        assert auth_client.get("/api/email-connection/").json()["connected"] is False
        c = EmailConnection(user=user, kind="imap", address="a@b.com", imap_host="h")
        c.set_secret("s")
        c.save()
        assert auth_client.get("/api/email-connection/").json()["address"] == "a@b.com"
        assert auth_client.delete("/api/email-connection/").status_code == 204
        assert not EmailConnection.objects.filter(user=user).exists()

    def test_test_endpoint_records_failure(self, auth_client, user):
        c = EmailConnection(user=user, kind="imap", address="a@b.com", imap_host="h")
        c.set_secret("s")
        c.save()
        with patch("apps.profiles.views.open_imap", side_effect=EmailProviderError("nope")):
            r = auth_client.post("/api/email-connection/test/")
        assert r.json()["ok"] is False
        c.refresh_from_db()
        assert c.last_error == "nope"


class TestGmailOAuth:
    @pytest.fixture(autouse=True)
    def _configured(self, settings):
        settings.GOOGLE_OAUTH_CLIENT_ID = "cid"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "sec"
        settings.GOOGLE_OAUTH_REDIRECT_URI = "https://api.example.com/api/email-connection/gmail/callback/"
        settings.FRONTEND_URL = "https://app.example.com"

    def test_authorize_unconfigured_says_so(self, auth_client, settings):
        settings.GOOGLE_OAUTH_CLIENT_ID = ""
        assert auth_client.get("/api/email-connection/gmail/authorize/").status_code == 501

    def test_authorize_returns_google_url_with_readonly_scope(self, auth_client):
        url = auth_client.get("/api/email-connection/gmail/authorize/").json()["url"]
        assert url.startswith("https://accounts.google.com/") and "gmail.readonly" in url and "state=" in url

    def _state(self, user):
        return signing.dumps({"u": str(user.id), "n": "x"}, salt="gmail-oauth-state")

    def test_callback_saves_refresh_token(self, api_client, user):
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "at", "refresh_token": "rt"})
        client.get.return_value = MagicMock(status_code=200, json=lambda: {"email": "me@gmail.com"})
        with patch("apps.profiles.views.httpx.Client", return_value=client):
            r = api_client.get("/api/email-connection/gmail/callback/", {"code": "c", "state": self._state(user)})
        assert r.status_code == 302 and r["Location"].endswith("/settings?gmail=connected")
        conn = EmailConnection.objects.get(user=user)
        assert conn.kind == "gmail" and conn.address == "me@gmail.com" and conn.get_secret() == "rt"

    def test_callback_rejects_forged_state(self, api_client, user):
        r = api_client.get("/api/email-connection/gmail/callback/", {"code": "c", "state": "forged"})
        assert r["Location"].endswith("gmail=error")
        assert not EmailConnection.objects.exists()

    def test_callback_user_denied(self, api_client):
        r = api_client.get("/api/email-connection/gmail/callback/", {"error": "access_denied"})
        assert r["Location"].endswith("gmail=denied")
