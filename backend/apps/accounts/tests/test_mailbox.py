import json
from datetime import datetime, timedelta, timezone as dt_tz
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from ai.base import AIProviderError
from ai.schemas import ChatMessage, CompletionResult
from apps.accounts.models import TemporaryAccount
from apps.email_service import service as email_service
from apps.email_service import textutil
from apps.email_service.models import EmailMessage, TemporaryEmail
from apps.email_service.schemas import MessageDetail, MessageSummary
from apps.identities.models import TemporaryIdentity
from apps.mcp_server.models import ApiKey
from apps.registration.models import RegistrationJob, TargetWebsite

pytestmark = pytest.mark.django_db


def make_account(user, domain="example.com", with_messages=True, provider="fake"):
    site = TargetWebsite.objects.create(domain=domain, registration_url=f"https://{domain}")
    identity = TemporaryIdentity.objects.create(
        user=user, name="N", email="a@b.co", expires_at=timezone.now() + timedelta(days=1))
    job = RegistrationJob.objects.create(user=user, target_website=site, identity=identity, state="completed")
    account = TemporaryAccount.objects.create(job=job, identity=identity, website=site)
    box = TemporaryEmail(identity=identity, provider=provider, address="a@b.co", expires_at=identity.expires_at)
    box.set_credential("{}")
    box.save()
    if with_messages:
        EmailMessage.objects.create(
            mailbox=box, external_id="m1", sender="Acme <hi@acme.io>", subject="Verify your email",
            html_body='<p>Hello</p><a href="https://acme.io/verify?a=1&amp;b=2">Verify</a><script>x()</script>',
            extracted_link="https://acme.io/verify?a=1&b=2", extracted_otp="123456",
            received_at=datetime(2026, 1, 1, tzinfo=dt_tz.utc),
        )
    return account, box


class FakeProvider:
    name = "fake"
    messages: dict = {}

    def get_messages(self, credential):
        return [MessageSummary(external_id=i) for i in self.messages]

    def get_message(self, credential, external_id):
        return self.messages[external_id]

    def extract_verification_link(self, message):
        return None

    def extract_otp(self, message):
        return None


class TestTextUtil:
    def test_html_becomes_plain_text_without_scripts(self):
        text = textutil.plain_text("", "<style>.a{}</style><p>Hi&nbsp;there</p><script>evil()</script><div>Bye</div>")
        assert "evil" not in text and "<" not in text and "Hi" in text and "Bye" in text

    def test_links_are_decoded_and_distinct(self):
        links = textutil.all_links("see https://x.io/a", '<a href="https://x.io/a">a</a><a href="https://x.io/b?c=1&amp;d=2">b</a>')
        assert links == ["https://x.io/a", "https://x.io/b?c=1&d=2"]


class TestMailboxApi:
    def test_list_shows_messages_and_unread(self, auth_client, user):
        account, _ = make_account(user)
        body = auth_client.get(f"/api/accounts/{account.id}/mailbox/").json()
        assert body["unread"] == 1 and body["mailbox"]["address"] == "a@b.co" and body["mailbox"]["status"] == "active"
        m = body["messages"][0]
        assert m["subject"] == "Verify your email" and m["has_link"] and m["has_code"] and "Hello" in m["snippet"]
        assert "html_body" not in m and "text_body" not in m

    def test_opening_a_message_marks_it_read_and_returns_text_only(self, auth_client, user):
        account, box = make_account(user)
        mid = EmailMessage.objects.get(mailbox=box).id
        body = auth_client.get(f"/api/accounts/{account.id}/mailbox/messages/{mid}/").json()
        assert body["verification_link"] == "https://acme.io/verify?a=1&b=2" and body["code"] == "123456"
        assert "https://acme.io/verify?a=1&b=2" in body["links"]
        assert "<script" not in body["text"] and "x()" not in body["text"]
        assert auth_client.get(f"/api/accounts/{account.id}/mailbox/").json()["unread"] == 0

    def test_refresh_fetches_new_mail(self, auth_client, user):
        account, _ = make_account(user, with_messages=False)
        fake = FakeProvider()
        fake.messages = {"n1": MessageDetail(external_id="n1", sender="x@y.z", subject="Welcome", text_body="hi")}
        with patch.object(email_service, "get_provider", return_value=fake):
            body = auth_client.get(f"/api/accounts/{account.id}/mailbox/?refresh=1").json()
        assert [m["subject"] for m in body["messages"]] == ["Welcome"]

    def test_refresh_failure_still_shows_saved_mail(self, auth_client, user):
        account, _ = make_account(user)
        with patch.object(email_service, "sync_new_messages", side_effect=RuntimeError("down")):
            body = auth_client.get(f"/api/accounts/{account.id}/mailbox/?refresh=1").json()
        assert len(body["messages"]) == 1 and body["refresh_error"]

    def test_other_users_cannot_read_it(self, other_auth_client, user):
        account, box = make_account(user)
        mid = EmailMessage.objects.get(mailbox=box).id
        assert other_auth_client.get(f"/api/accounts/{account.id}/mailbox/").status_code == 404
        assert other_auth_client.get(f"/api/accounts/{account.id}/mailbox/messages/{mid}/").status_code == 404
        assert other_auth_client.post(f"/api/accounts/{account.id}/mailbox/ask/", {"question": "hello?"}, format="json").status_code == 404

    def test_deleting_the_account_erases_the_inbox(self, auth_client, user):
        account, box = make_account(user)
        assert auth_client.delete(f"/api/accounts/{account.id}/").status_code == 204
        assert EmailMessage.objects.filter(mailbox=box).count() == 0
        assert auth_client.get(f"/api/accounts/{account.id}/mailbox/").status_code == 410

    def test_expiry_erases_the_inbox(self, user):
        from apps.identities.tasks import expire_temporary_identities

        account, box = make_account(user)
        TemporaryIdentity.objects.filter(pk=account.identity_id).update(expires_at=timezone.now() - timedelta(minutes=1))
        expire_temporary_identities()
        assert EmailMessage.objects.filter(mailbox=box).count() == 0
        from apps.notifications.models import Notification
        assert Notification.objects.filter(user=user, kind="account_expired").count() == 1


def completion(text):
    return CompletionResult(message=ChatMessage(role="assistant", content=text), provider="t", model="m")


class TestAskTheAgent:
    def test_answers_from_the_emails_with_no_tools(self, auth_client, user):
        account, _ = make_account(user)
        provider = MagicMock()
        provider.complete.return_value = completion("Yes, code 123456 arrived from Acme.")
        with patch("apps.email_service.assistant.get_ai_provider", return_value=provider), \
             patch.object(email_service, "get_provider", return_value=FakeProvider()):
            r = auth_client.post(f"/api/accounts/{account.id}/mailbox/ask/",
                                 {"question": "Did the code arrive?"}, format="json")
        assert r.status_code == 200 and "123456" in r.json()["answer"] and r.json()["checked"] == 1
        messages, tools = provider.complete.call_args.args
        assert tools == []  # untrusted email content must never have tools to steer
        assert "UNTRUSTED" in messages[0].content and "Did the code arrive?" in messages[1].content
        assert "https://acme.io/verify" in messages[1].content and "x()" not in messages[1].content

    def test_empty_inbox_needs_no_ai_call(self, auth_client, user):
        account, _ = make_account(user, with_messages=False)
        with patch("apps.email_service.assistant.get_ai_provider") as gp, \
             patch.object(email_service, "get_provider", return_value=FakeProvider()):
            r = auth_client.post(f"/api/accounts/{account.id}/mailbox/ask/", {"question": "Anything yet?"}, format="json")
        gp.assert_not_called()
        assert "empty" in r.json()["answer"].lower()

    def test_provider_outage_is_a_503_not_a_crash(self, auth_client, user):
        account, _ = make_account(user)
        provider = MagicMock()
        provider.complete.side_effect = AIProviderError("rate limited", retryable=True)
        with patch("apps.email_service.assistant.get_ai_provider", return_value=provider), \
             patch.object(email_service, "get_provider", return_value=FakeProvider()):
            r = auth_client.post(f"/api/accounts/{account.id}/mailbox/ask/", {"question": "Anything?"}, format="json")
        assert r.status_code == 503

    def test_short_question_rejected(self, auth_client, user):
        account, _ = make_account(user)
        assert auth_client.post(f"/api/accounts/{account.id}/mailbox/ask/", {"question": "?"}, format="json").status_code == 400


class TestMcpMailboxTools:
    @pytest.fixture
    def mcp(self, api_client, user):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {ApiKey.create_for(user, 'c')[1]}")

        def call(name, **args):
            r = api_client.post("/mcp/", {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                          "params": {"name": name, "arguments": args}}, format="json")
            result = r.json()["result"]
            return json.loads(result["content"][0]["text"]), result["isError"]

        return call

    def test_list_accounts_has_no_secrets(self, mcp, user):
        make_account(user)
        out, err = mcp("list_accounts")
        assert not err and out["accounts"][0]["site"] == "example.com"
        assert "password" not in json.dumps(out).lower() and "a@b.co" not in json.dumps(out)

    def test_check_mailbox_returns_messages_and_a_warning(self, mcp, user):
        account, _ = make_account(user)
        with patch.object(email_service, "get_provider", return_value=FakeProvider()):
            out, err = mcp("check_mailbox", account_id=str(account.id))
        assert not err and out["messages"][0]["code"] == "123456" and "untrusted" in out["warning"].lower()
        assert "<script" not in json.dumps(out)

    def test_check_mailbox_other_users_account(self, mcp, other_user):
        account, _ = make_account(other_user)
        out, err = mcp("check_mailbox", account_id=str(account.id))
        assert err and "No such account" in json.dumps(out)
