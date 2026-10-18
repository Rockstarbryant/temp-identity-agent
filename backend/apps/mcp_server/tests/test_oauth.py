import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.utils import timezone

from apps.mcp_server.models import ApiKey, OAuthCode, OAuthGrant

pytestmark = pytest.mark.django_db

REDIRECT = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}


def register(client, uris=None):
    r = client.post("/oauth/register", {"client_name": "Claude", "redirect_uris": uris or [REDIRECT]}, format="json")
    assert r.status_code == 201, r.content
    return r.json()["client_id"]


def authorize_params(client_id, **over):
    p = {"client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code", "state": "xyz",
         "code_challenge": CHALLENGE, "code_challenge_method": "S256"}
    p.update(over)
    return p


def approve(auth_client, client_id, **over):
    r = auth_client.post("/api/oauth/approve/", {**authorize_params(client_id), "approve": True, **over}, format="json")
    assert r.status_code == 200, r.content
    return parse_qs(urlparse(r.json()["redirect_url"]).query)


def token(client, **data):
    return client.post("/oauth/token", urlencode(data), content_type="application/x-www-form-urlencoded")


def full_flow(api_client, auth_client):
    cid = register(api_client)
    code = approve(auth_client, cid)["code"][0]
    r = token(api_client, grant_type="authorization_code", code=code, redirect_uri=REDIRECT, code_verifier=VERIFIER, client_id=cid)
    assert r.status_code == 200, r.content
    return cid, r.json()


class TestDiscovery:
    def test_unauthenticated_mcp_points_to_metadata(self, api_client):
        r = api_client.post("/mcp/", INIT, format="json")
        assert r.status_code == 401
        assert 'resource_metadata="http://testserver/.well-known/oauth-protected-resource"' in r["WWW-Authenticate"]

    def test_metadata_documents(self, api_client):
        prm = api_client.get("/.well-known/oauth-protected-resource").json()
        assert prm["resource"] == "http://testserver/mcp/" and prm["authorization_servers"] == ["http://testserver"]
        assert api_client.get("/.well-known/oauth-protected-resource/mcp/").status_code == 200
        asm = api_client.get("/.well-known/oauth-authorization-server").json()
        assert asm["code_challenge_methods_supported"] == ["S256"]
        assert asm["registration_endpoint"].endswith("/oauth/register")
        assert asm["token_endpoint"].endswith("/oauth/token")

    def test_configured_public_url_wins(self, api_client, settings):
        settings.BACKEND_PUBLIC_URL = "https://logindirect.onrender.com/"
        assert api_client.get("/.well-known/oauth-authorization-server").json()["issuer"] == "https://logindirect.onrender.com"


class TestRegistration:
    def test_rejects_bad_redirects(self, api_client):
        for bad in (["http://evil.example/cb"], ["javascript:alert(1)"], [], "https://x", ["https://a.example/cb#frag"]):
            r = api_client.post("/oauth/register", {"redirect_uris": bad}, format="json")
            assert r.status_code == 400 and r.json()["error"] == "invalid_redirect_uri"

    def test_localhost_allowed(self, api_client):
        register(api_client, ["http://localhost:6274/callback"])


class TestAuthorize:
    def test_redirects_to_web_app(self, api_client, settings):
        settings.FRONTEND_URL = "https://app.example"
        cid = register(api_client)
        r = api_client.get("/oauth/authorize", authorize_params(cid))
        assert r.status_code == 302 and r["Location"].startswith("https://app.example/oauth/authorize?")
        assert "code_challenge=" in r["Location"] and "state=xyz" in r["Location"]

    def test_unknown_redirect_is_not_followed(self, api_client):
        cid = register(api_client)
        r = api_client.get("/oauth/authorize", authorize_params(cid, redirect_uri="https://evil.example/cb"))
        assert r.status_code == 400

    def test_pkce_is_required(self, api_client):
        cid = register(api_client)
        r = api_client.get("/oauth/authorize", authorize_params(cid, code_challenge_method="plain"))
        assert r.status_code == 302 and "error=invalid_request" in r["Location"] and r["Location"].startswith(REDIRECT)

    def test_info_and_deny(self, api_client, auth_client):
        cid = register(api_client)
        info = auth_client.get("/api/oauth/authorize-info/", authorize_params(cid))
        assert info.status_code == 200 and info.json()["client_name"] == "Claude"
        r = auth_client.post("/api/oauth/approve/", {**authorize_params(cid), "approve": False}, format="json")
        assert "error=access_denied" in r.json()["redirect_url"] and "state=xyz" in r.json()["redirect_url"]
        assert not OAuthCode.objects.exists()

    def test_approval_needs_login(self, api_client):
        cid = register(api_client)
        assert api_client.post("/api/oauth/approve/", {**authorize_params(cid), "approve": True}, format="json").status_code == 401


class TestTokens:
    def test_full_flow_then_mcp_works(self, api_client, auth_client, user):
        cid, tokens = full_flow(api_client, auth_client)
        assert tokens["token_type"] == "Bearer" and tokens["expires_in"] == 3600 and tokens["refresh_token"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
        r = api_client.post("/mcp/", INIT, format="json")
        assert r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "temp-identity-agent"
        key = ApiKey.objects.get(user=user, kind="oauth")
        assert key.expires_at > timezone.now()

    def test_json_body_also_works(self, api_client, auth_client):
        cid = register(api_client)
        code = approve(auth_client, cid)["code"][0]
        r = api_client.post("/oauth/token", {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                                            "code_verifier": VERIFIER, "client_id": cid}, format="json")
        assert r.status_code == 200

    def test_code_is_single_use(self, api_client, auth_client):
        cid = register(api_client)
        code = approve(auth_client, cid)["code"][0]
        args = dict(grant_type="authorization_code", code=code, redirect_uri=REDIRECT, code_verifier=VERIFIER, client_id=cid)
        assert token(api_client, **args).status_code == 200
        assert token(api_client, **args).json()["error"] == "invalid_grant"

    def test_wrong_verifier_redirect_client_and_expiry(self, api_client, auth_client):
        cid = register(api_client)
        other = register(api_client)
        base = dict(grant_type="authorization_code", redirect_uri=REDIRECT, client_id=cid)
        code = approve(auth_client, cid)["code"][0]
        assert token(api_client, **base, code=code, code_verifier="w" * 64).json()["error"] == "invalid_grant"
        code = approve(auth_client, cid)["code"][0]
        assert token(api_client, **{**base, "redirect_uri": "https://other.example/cb"}, code=code, code_verifier=VERIFIER).status_code == 400
        code = approve(auth_client, cid)["code"][0]
        assert token(api_client, **{**base, "client_id": other}, code=code, code_verifier=VERIFIER).status_code == 400
        code = approve(auth_client, cid)["code"][0]
        OAuthCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        assert token(api_client, **base, code=code, code_verifier=VERIFIER).status_code == 400
        assert token(api_client, grant_type="authorization_code", client_id="nope", code="x").status_code == 401

    def test_refresh_rotates_and_revokes_old_access(self, api_client, auth_client):
        cid, first = full_flow(api_client, auth_client)
        r = token(api_client, grant_type="refresh_token", refresh_token=first["refresh_token"], client_id=cid)
        assert r.status_code == 200
        second = r.json()
        assert second["access_token"] != first["access_token"] and second["refresh_token"] != first["refresh_token"]
        # old refresh token no longer works; old access token is revoked
        assert token(api_client, grant_type="refresh_token", refresh_token=first["refresh_token"], client_id=cid).status_code == 400
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {first['access_token']}")
        assert api_client.post("/mcp/", INIT, format="json").status_code == 401
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {second['access_token']}")
        assert api_client.post("/mcp/", INIT, format="json").status_code == 200

    def test_expired_access_token_is_rejected(self, api_client, auth_client):
        cid, tokens = full_flow(api_client, auth_client)
        ApiKey.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
        assert api_client.post("/mcp/", INIT, format="json").status_code == 401
        # ...but the refresh token still renews it
        api_client.credentials()
        assert token(api_client, grant_type="refresh_token", refresh_token=tokens["refresh_token"], client_id=cid).status_code == 200

    def test_revoking_in_settings_disconnects_the_client(self, api_client, auth_client, user):
        cid, tokens = full_flow(api_client, auth_client)
        key = ApiKey.objects.get(user=user, kind="oauth")
        assert auth_client.delete(f"/api/api-keys/{key.id}/").status_code == 204
        api_client.credentials()
        assert token(api_client, grant_type="refresh_token", refresh_token=tokens["refresh_token"], client_id=cid).status_code == 400

    def test_refresh_token_belongs_to_its_client(self, api_client, auth_client):
        cid, tokens = full_flow(api_client, auth_client)
        other = register(api_client)
        assert token(api_client, grant_type="refresh_token", refresh_token=tokens["refresh_token"], client_id=other).status_code == 400

    def test_oauth_keys_do_not_count_against_manual_limit(self, api_client, auth_client):
        full_flow(api_client, auth_client)
        for i in range(10):
            assert auth_client.post("/api/api-keys/", {"name": f"k{i}"}, format="json").status_code == 201
        listing = auth_client.get("/api/api-keys/").json()
        assert {k["kind"] for k in listing} == {"manual", "oauth"}
