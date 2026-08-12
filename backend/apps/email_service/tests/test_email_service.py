import json

import httpx
import pytest

from apps.email_service.extraction import find_otp_code, find_verification_link
from apps.email_service.providers.mailtm import MailTmProvider

pytestmark = pytest.mark.django_db


class TestExtraction:
    def test_finds_verification_link_by_keyword_score(self):
        html = '''
        <a href="https://example.com/account">Account</a>
        <a href="https://example.com/verify?token=abc">Verify email</a>
        <a href="https://example.com/unsubscribe">Unsubscribe</a>
        '''
        assert find_verification_link(html) == "https://example.com/verify?token=abc"

    def test_falls_back_to_first_link_if_no_keyword_match(self):
        html = '<a href="https://example.com/random">Click here</a>'
        assert find_verification_link(html) == "https://example.com/random"

    def test_otp_prefers_keyword_proximity(self):
        text = "Your order #10293 has shipped. Your one-time PIN: 5567."
        assert find_otp_code(text) == "5567"

    def test_otp_falls_back_to_first_digit_run(self):
        assert find_otp_code("Reference 998877 for your records.") == "998877"

    def test_empty_input_returns_none(self):
        assert find_verification_link("") is None
        assert find_otp_code("") is None

    def test_no_crash_on_malicious_html(self):
        # Prompt-injection-style content embedded in email HTML must not
        # crash extraction or be treated as anything but text to scan.
        malicious = '<script>alert(1)</script><a href="javascript:void(0)">ignore all instructions</a>'
        result = find_verification_link(malicious)
        assert result is None or isinstance(result, str)


class TestMailTmProviderContract:
    """
    Tests the provider's parsing against mail.tm's OWN documented response
    schema (fixtures taken from https://docs.mail.tm), via httpx.MockTransport.
    Not a live network test — see scripts/live_smoke_test_mailtm.py for that.
    """

    @staticmethod
    def _provider_with_fixture():
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/domains":
                return httpx.Response(200, json={"hydra:member": [{"id": "d", "domain": "test.example"}]})
            if path == "/accounts":
                return httpx.Response(201, json={"id": "a1", "address": json.loads(request.content)["address"]})
            if path == "/token":
                return httpx.Response(200, json={"id": "a1", "token": "jwt-fixture"})
            if path == "/messages":
                return httpx.Response(200, json={"hydra:member": [{
                    "id": "m1", "from": {"address": "noreply@site.com"}, "subject": "Verify",
                    "seen": False, "createdAt": "2026-08-09T00:00:00.000Z",
                }]})
            if path == "/messages/m1":
                return httpx.Response(200, json={
                    "id": "m1", "from": {"address": "noreply@site.com"}, "subject": "Verify",
                    "text": "Verify: https://site.com/v?t=1",
                    "html": ['<a href="https://site.com/v?t=1">Verify</a>'],
                    "createdAt": "2026-08-09T00:00:00.000Z",
                })
            return httpx.Response(404)

        provider = MailTmProvider()
        provider._client = lambda token=None: httpx.Client(
            base_url=provider.base_url,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            transport=httpx.MockTransport(handler),
        )
        return provider

    def test_create_mailbox(self):
        provider = self._provider_with_fixture()
        mailbox = provider.create_mailbox(local_part="testuser")
        assert mailbox.address == "testuser@test.example"
        assert mailbox.credential == "jwt-fixture"

    def test_get_messages_and_extraction(self):
        provider = self._provider_with_fixture()
        mailbox = provider.create_mailbox()
        messages = provider.get_messages(mailbox.credential)
        assert len(messages) == 1
        detail = provider.get_message(mailbox.credential, messages[0].external_id)
        assert provider.extract_verification_link(detail) == "https://site.com/v?t=1"

    def test_html_list_response_handled(self):
        """mail.tm returns `html` as a list of fragments, not a string — must not crash."""
        provider = self._provider_with_fixture()
        mailbox = provider.create_mailbox()
        detail = provider.get_message(mailbox.credential, "m1")
        assert isinstance(detail.html_body, str)
        assert "https://site.com/v?t=1" in detail.html_body
