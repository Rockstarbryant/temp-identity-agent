import json
from unittest.mock import patch

import pytest

from apps.mcp_server.models import ApiKey
from apps.registration.models import AgentQuestion, RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_dns_no_worker():
    with patch("apps.common.url_safety.validate_url", side_effect=lambda u: u), \
         patch("apps.registration.tasks.run_registration_job_task.delay") as delay:
        yield delay


@pytest.fixture
def key(user):
    return ApiKey.create_for(user, "Claude Desktop")[1]


@pytest.fixture
def mcp(api_client, key):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {key}")

    def rpc(method, params=None, id=1, client=api_client):
        body = {"jsonrpc": "2.0", "method": method, **({"id": id} if id is not None else {}), **({"params": params} if params else {})}
        return client.post("/mcp/", body, format="json")

    return rpc


def tool(mcp, name, **args):
    r = mcp("tools/call", {"name": name, "arguments": args})
    assert r.status_code == 200
    result = r.json()["result"]
    return json.loads(result["content"][0]["text"]), result["isError"]


class TestAuth:
    def test_no_key_is_rejected(self, api_client):
        assert api_client.post("/mcp/", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, format="json").status_code == 401

    def test_garbage_and_revoked_keys_rejected(self, api_client, user):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer tia_notarealkey")
        assert api_client.post("/mcp/", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, format="json").status_code == 401
        k, raw = ApiKey.create_for(user, "x")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        assert api_client.post("/mcp/", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, format="json").status_code == 200
        from django.utils import timezone

        ApiKey.objects.filter(id=k.id).update(revoked_at=timezone.now())
        assert api_client.post("/mcp/", {"jsonrpc": "2.0", "id": 1, "method": "ping"}, format="json").status_code == 401

    def test_only_a_hash_is_stored_and_last_used_updates(self, user, key, mcp):
        stored = ApiKey.objects.get(user=user)
        assert key not in stored.key_hash and stored.key_hash == ApiKey.hash_key(key)
        mcp("ping")
        stored.refresh_from_db()
        assert stored.last_used_at is not None

    def test_get_is_not_supported(self, api_client, key):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {key}")
        assert api_client.get("/mcp/").status_code == 405


class TestProtocol:
    def test_initialize(self, mcp):
        body = mcp("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}}).json()
        assert body["result"]["protocolVersion"] == "2025-03-26"
        assert "tools" in body["result"]["capabilities"] and body["result"]["serverInfo"]["name"]

    def test_unknown_version_falls_back_to_latest(self, mcp):
        assert mcp("initialize", {"protocolVersion": "1999-01-01"}).json()["result"]["protocolVersion"] == "2025-06-18"

    def test_notification_gets_202(self, mcp):
        assert mcp("notifications/initialized", id=None).status_code == 202

    def test_tools_list_has_schemas(self, mcp):
        tools = mcp("tools/list").json()["result"]["tools"]
        names = {t["name"] for t in tools}
        assert {"register_on_site", "get_job", "answer_question", "cancel_job", "list_jobs", "list_accounts", "check_mailbox"} <= names
        assert all(t["inputSchema"]["type"] == "object" and t["description"] for t in tools)
        assert "get_credentials" not in names  # credentials are never exposed to remote clients

    def test_errors(self, mcp):
        assert mcp("nope/method").json()["error"]["code"] == -32601
        assert mcp("tools/call", {"name": "does_not_exist"}).json()["error"]["code"] == -32602

    def test_bad_json(self, api_client, key):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {key}")
        r = api_client.post("/mcp/", data="{not json", content_type="application/json")
        assert r.status_code == 400 and r.json()["error"]["code"] == -32700

    def test_batch(self, mcp, api_client):
        r = api_client.post("/mcp/", [{"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                      {"jsonrpc": "2.0", "method": "notifications/initialized"}], format="json")
        assert r.status_code == 200 and len(r.json()) == 1


class TestTools:
    def test_register_creates_mcp_job_with_goal(self, mcp, user, _no_dns_no_worker):
        out, is_error = tool(mcp, "register_on_site", url="https://shop.example.com", extraction_goal="my order history")
        assert not is_error and out["state"] == "queued" and out["ui_url"].endswith(f"/jobs/{out['job_id']}")
        job = RegistrationJob.objects.get(id=out["job_id"])
        assert job.source == "mcp" and job.goal == "my order history" and job.target_url == "https://shop.example.com"
        _no_dns_no_worker.assert_called_once()
        assert "email + password" in out["message"]

    def test_register_validation(self, mcp):
        out, is_error = tool(mcp, "register_on_site")
        assert is_error and "url" in out["error"]
        out, is_error = tool(mcp, "register_on_site", url="https://x.com", account_mode="weird")
        assert is_error
        out, is_error = tool(mcp, "register_on_site", url="https://x.com", account_mode="permanent")
        assert is_error and "Settings" in out["error"]

    def test_unsafe_url_refused(self, mcp):
        from apps.common.exceptions import UnsafeURLError

        with patch("apps.common.url_safety.validate_url", side_effect=UnsafeURLError("Access to 'localhost' is not allowed.")):
            out, is_error = tool(mcp, "register_on_site", url="http://localhost/admin")
        assert is_error and "not allowed" in out["error"]

    def test_unsupported_site_is_explained_to_the_agent(self, mcp, user):
        out, _ = tool(mcp, "register_on_site", url="https://social-only.example.com")
        RegistrationJob.objects.filter(id=out["job_id"]).update(
            state="failed", error_code="AUTH_METHOD_UNSUPPORTED", auth_check={"email_password": False, "methods": ["google"]},
            error_message="This site doesn't offer sign-up or login with an email and password (google).",
        )
        got, is_error = tool(mcp, "get_job", job_id=out["job_id"])
        assert not is_error and got["finished"] and got["error_code"] == "AUTH_METHOD_UNSUPPORTED"
        assert "email and password" in got["error_message"] and got["sign_in_methods"]["methods"] == ["google"]

    def test_completed_job_returns_result_but_no_credentials(self, mcp, user):
        out, _ = tool(mcp, "register_on_site", url="https://shop.example.com")
        RegistrationJob.objects.filter(id=out["job_id"]).update(state="completed", result={"summary": "s", "data": {"a": 1}})
        got, _ = tool(mcp, "get_job", job_id=out["job_id"])
        assert got["result"] == {"summary": "s", "data": {"a": 1}}
        assert "password" not in json.dumps(got).lower()

    def test_pending_question_and_answer(self, mcp, user):
        out, _ = tool(mcp, "register_on_site", url="https://shop.example.com")
        job = RegistrationJob.objects.get(id=out["job_id"])
        job.state = "waiting_for_user"
        job.save()
        q = AgentQuestion.objects.create(job=job, key="phone", question="Phone number?")
        got, _ = tool(mcp, "get_job", job_id=out["job_id"])
        assert got["pending_question"]["question_id"] == str(q.id)
        ans, is_error = tool(mcp, "answer_question", job_id=out["job_id"], question_id=str(q.id), answer="0712345678")
        assert not is_error and ans["accepted"]
        q.refresh_from_db()
        assert q.get_answer() == "0712345678"
        _, is_error = tool(mcp, "answer_question", job_id=out["job_id"], question_id=str(q.id), answer="again")
        assert is_error

    def test_captcha_state_points_the_human_to_the_ui(self, mcp):
        out, _ = tool(mcp, "register_on_site", url="https://shop.example.com")
        RegistrationJob.objects.filter(id=out["job_id"]).update(state="captcha_required")
        got, _ = tool(mcp, "get_job", job_id=out["job_id"])
        assert "ui_url" in got["next"] and "CAPTCHA" in got["next"]

    def test_cancel_and_list(self, mcp):
        out, _ = tool(mcp, "register_on_site", url="https://shop.example.com")
        assert tool(mcp, "cancel_job", job_id=out["job_id"])[0]["state"] == "cancelled"
        assert [j["job_id"] for j in tool(mcp, "list_jobs")[0]["jobs"]] == [out["job_id"]]

    def test_cannot_see_other_users_jobs(self, mcp, other_user):
        site = TargetWebsite.objects.create(domain="x.com", registration_url="https://x.com")
        theirs = RegistrationJob.objects.create(user=other_user, target_website=site)
        out, is_error = tool(mcp, "get_job", job_id=str(theirs.id))
        assert is_error and out["error"] == "No such job."
        assert tool(mcp, "get_job", job_id="not-a-uuid")[1] is True


class TestKeyManagement:
    def test_create_list_revoke(self, auth_client, user):
        r = auth_client.post("/api/api-keys/", {"name": "Cursor"}, format="json")
        assert r.status_code == 201 and r.json()["key"].startswith("tia_")
        listed = auth_client.get("/api/api-keys/").json()
        assert len(listed) == 1 and "key" not in listed[0] and listed[0]["name"] == "Cursor"
        assert auth_client.delete(f"/api/api-keys/{listed[0]['id']}/").status_code == 204
        assert auth_client.get("/api/api-keys/").json() == []
        assert auth_client.delete(f"/api/api-keys/{listed[0]['id']}/").status_code == 404

    def test_cap_on_active_keys(self, auth_client):
        for i in range(10):
            assert auth_client.post("/api/api-keys/", {"name": f"k{i}"}, format="json").status_code == 201
        assert auth_client.post("/api/api-keys/", {"name": "one more"}, format="json").status_code == 400

    def test_cannot_revoke_someone_elses_key(self, auth_client, other_user):
        k, _ = ApiKey.create_for(other_user, "theirs")
        assert auth_client.delete(f"/api/api-keys/{k.id}/").status_code == 404


class TestAcceptHeaders:
    """MCP clients send Accept: text/event-stream; that must never produce a 406."""

    BODY = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}

    @pytest.mark.parametrize("accept", ["application/json, text/event-stream", "text/event-stream", "*/*", "application/json"])
    def test_post_works_for_any_accept(self, mcp, api_client, accept):
        r = api_client.post("/mcp/", self.BODY, format="json", HTTP_ACCEPT=accept)
        assert r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "temp-identity-agent"

    @pytest.mark.parametrize("accept", ["text/event-stream", "application/json", "*/*"])
    def test_get_stream_is_405_not_406(self, mcp, api_client, accept):
        r = api_client.get("/mcp/", HTTP_ACCEPT=accept)
        assert r.status_code == 405

    def test_delete_is_405(self, mcp, api_client):
        assert api_client.delete("/mcp/", HTTP_ACCEPT="text/event-stream").status_code == 405
