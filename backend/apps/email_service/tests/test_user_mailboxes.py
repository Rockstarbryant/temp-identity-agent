import base64
import json
from email.message import EmailMessage as PyEmail
from unittest.mock import MagicMock, patch

import pytest

from apps.email_service.providers.base import EmailProviderError
from apps.email_service.providers.rfc822 import parse_rfc822
from apps.email_service.providers.user_gmail import GmailUserMailboxProvider
from apps.email_service.providers.user_imap import ImapUserMailboxProvider, current_uid_baseline, preset_host
from apps.profiles.models import EmailConnection

pytestmark = pytest.mark.django_db


def _raw(subject="Verify your account", text="Your code is 482913", html=None) -> bytes:
    m = PyEmail()
    m["From"] = "noreply@site.com"
    m["To"] = "me@example.com"
    m["Subject"] = subject
    m["Date"] = "Sat, 17 Oct 2026 10:00:00 +0000"
    m.set_content(text)
    if html:
        m.add_alternative(html, subtype="html")
    return m.as_bytes()


class FakeImap:
    """Just enough of imaplib.IMAP4_SSL; messages is {uid: raw bytes}."""

    def __init__(self, messages):
        self.messages = messages

    def select(self, *a, **k):
        return "OK", [b"1"]

    def status(self, mailbox, what):
        return "OK", [f"INBOX (UIDNEXT {max(self.messages, default=0) + 1})".encode()]

    def uid(self, cmd, *args):
        if cmd == "SEARCH":
            lo = int(args[1].split()[1].split(":")[0])
            hits = [u for u in self.messages if u >= lo] or ([max(self.messages)] if self.messages else [])
            return "OK", [" ".join(str(u) for u in hits).encode()]
        if cmd == "FETCH":
            return "OK", [(b"1 (BODY[] {n}", self.messages[int(args[0])]), b")"]
        raise AssertionError(cmd)

    def close(self):
        pass

    def logout(self):
        pass


@pytest.fixture
def connection(user):
    c = EmailConnection(user=user, kind="imap", address="me@example.com", imap_host="imap.example.com")
    c.set_secret("app-password")
    c.save()
    return c


class TestParse:
    def test_plain_and_html(self):
        d = parse_rfc822(_raw(html="<p>Your code is <b>482913</b></p>"), "7")
        assert d.subject == "Verify your account"
        assert "482913" in d.text_body and "<b>482913</b>" in d.html_body
        assert d.received_at is not None and d.external_id == "7"

    def test_garbage_does_not_crash(self):
        assert parse_rfc822(b"not an email at all", "1").external_id == "1"


class TestImapProvider:
    def test_preset_hosts(self):
        assert preset_host("a@gmail.com") == "imap.gmail.com"
        assert preset_host("a@unknown.org") == ""

    def test_baseline_is_highest_uid(self):
        assert current_uid_baseline(FakeImap({3: b"", 9: b""})) == 9

    def test_only_messages_after_baseline_are_visible(self, connection):
        cred = json.dumps({"connection_id": str(connection.id), "baseline_uid": 2})
        fake = FakeImap({1: _raw("old one"), 2: _raw("old two"), 3: _raw("new code")})
        with patch("apps.email_service.providers.user_imap.open_imap", return_value=fake):
            msgs = ImapUserMailboxProvider().get_messages(cred)
            assert [m.subject for m in msgs] == ["new code"]
            with pytest.raises(EmailProviderError):
                ImapUserMailboxProvider().get_message(cred, "2")  # arrived before the job
            assert ImapUserMailboxProvider().get_message(cred, "3").subject == "new code"

    def test_wait_returns_newest_or_none(self, connection):
        cred = json.dumps({"connection_id": str(connection.id), "baseline_uid": 0})
        fake = FakeImap({1: _raw("first"), 2: _raw("second")})
        with patch("apps.email_service.providers.user_imap.open_imap", return_value=fake):
            assert ImapUserMailboxProvider().wait_for_message(cred, timeout_seconds=1).subject == "second"
        empty = FakeImap({})
        with patch("apps.email_service.providers.user_imap.open_imap", return_value=empty), \
             patch("apps.email_service.providers.user_imap.time.sleep"):
            assert ImapUserMailboxProvider().wait_for_message(cred, timeout_seconds=0) is None

    def test_removed_connection_gives_clear_error(self, connection):
        cred = json.dumps({"connection_id": str(connection.id), "baseline_uid": 0})
        connection.delete()
        with pytest.raises(EmailProviderError, match="removed"):
            ImapUserMailboxProvider().get_messages(cred)


class TestGmailProvider:
    @pytest.fixture
    def gconn(self, user, settings):
        settings.GOOGLE_OAUTH_CLIENT_ID = "cid"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "sec"
        c = EmailConnection(user=user, kind="gmail", address="me@gmail.com")
        c.set_secret("refresh-token")
        c.save()
        return c

    def _client(self, raw_by_id):
        client = MagicMock()
        client.__enter__.return_value = client

        def post(url, data=None, **k):
            assert data["refresh_token"] == "refresh-token"
            return MagicMock(status_code=200, json=lambda: {"access_token": "at", "expires_in": 3600})

        def get(url, params=None, headers=None):
            assert headers["Authorization"] == "Bearer at"
            if url.endswith("/messages"):
                assert params["q"].startswith("after:1000")
                return MagicMock(status_code=200, json=lambda: {"messages": [{"id": i} for i in raw_by_id]})
            mid = url.rsplit("/", 1)[1]
            enc = base64.urlsafe_b64encode(raw_by_id[mid]).decode().rstrip("=")
            return MagicMock(status_code=200, json=lambda: {"raw": enc})

        client.post.side_effect = post
        client.get.side_effect = get
        return client

    def test_lists_and_reads_with_baseline(self, gconn):
        cred = json.dumps({"connection_id": str(gconn.id), "baseline_ts": 1000})
        client = self._client({"m2": _raw("newest"), "m1": _raw("older")})
        with patch("apps.email_service.providers.user_gmail._client", return_value=client):
            p = GmailUserMailboxProvider()
            assert [m.subject for m in p.get_messages(cred)] == ["newest", "older"]
            assert p.wait_for_message(cred, timeout_seconds=1).subject == "newest"
            assert p.get_message(cred, "m1").subject == "older"

    def test_revoked_token_is_reported(self, gconn):
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = MagicMock(status_code=400)
        with patch("apps.email_service.providers.user_gmail._client", return_value=client):
            from apps.email_service.providers.user_gmail import get_access_token

            with pytest.raises(EmailProviderError, match="Reconnect"):
                get_access_token(gconn)
