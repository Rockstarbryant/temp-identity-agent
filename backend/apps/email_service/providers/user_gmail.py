"""
Reads the user's Gmail through the Gmail API with read-only access (OAuth refresh token).

Like the IMAP reader, it only returns messages received after the job started
(`baseline_ts`, epoch seconds). Credential string is JSON:
{"connection_id": "...", "baseline_ts": 1760000000}.
"""
import base64
import json
import time

import httpx
from django.conf import settings
from django.core.cache import cache

from apps.email_service.providers.base import EmailProvider, EmailProviderError
from apps.email_service.providers.rfc822 import parse_rfc822
from apps.email_service.schemas import MessageDetail, MessageSummary

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_LISTED = 10


def _client() -> httpx.Client:  # patched in tests
    return httpx.Client(timeout=20.0)


def get_access_token(connection) -> str:
    cache_key = f"gmail_at:{connection.id}"
    token = cache.get(cache_key)
    if token:
        return token
    with _client() as client:
        resp = client.post(TOKEN_URL, data={
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": connection.get_secret(),
            "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        raise EmailProviderError(
            "Google rejected the saved sign-in (it may have been revoked). Reconnect Gmail in Settings."
        )
    body = resp.json()
    token = body["access_token"]
    cache.set(cache_key, token, max(int(body.get("expires_in", 3600)) - 120, 60))
    return token


class GmailUserMailboxProvider(EmailProvider):
    name = "gmail"

    def create_mailbox(self, local_part=None):  # pragma: no cover - not applicable
        raise EmailProviderError("Gmail mailboxes are connected by the user, not created.")

    def _info(self, credential: str):
        from apps.profiles.models import EmailConnection

        info = json.loads(credential)
        try:
            conn = EmailConnection.objects.get(id=info["connection_id"])
        except EmailConnection.DoesNotExist as exc:
            raise EmailProviderError("The connected mailbox was removed in Settings.") from exc
        return conn, int(info.get("baseline_ts", 0))

    def _get(self, client, token, path, **params):
        resp = client.get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code != 200:
            raise EmailProviderError(f"Gmail returned {resp.status_code}.")
        return resp.json()

    def _list_ids(self, client, token, baseline_ts: int) -> list[str]:
        data = self._get(client, token, "/messages", q=f"after:{baseline_ts} in:anywhere", maxResults=MAX_LISTED)
        return [m["id"] for m in data.get("messages", [])]  # newest first

    def _fetch(self, client, token, message_id: str) -> MessageDetail:
        data = self._get(client, token, f"/messages/{message_id}", format="raw")
        raw = base64.urlsafe_b64decode(data["raw"] + "=" * (-len(data["raw"]) % 4))
        return parse_rfc822(raw, message_id)

    def get_messages(self, credential: str) -> list[MessageSummary]:
        conn, baseline = self._info(credential)
        token = get_access_token(conn)
        with _client() as client:
            out = []
            for mid in self._list_ids(client, token, baseline):
                d = self._fetch(client, token, mid)
                out.append(MessageSummary(external_id=mid, sender=d.sender, subject=d.subject, received_at=d.received_at))
            return out

    def get_message(self, credential: str, external_id: str) -> MessageDetail:
        conn, baseline = self._info(credential)
        token = get_access_token(conn)
        with _client() as client:
            return self._fetch(client, token, external_id)

    def wait_for_message(self, credential, timeout_seconds=60, poll_interval_seconds=4.0):
        conn, baseline = self._info(credential)
        token = get_access_token(conn)
        deadline = time.monotonic() + timeout_seconds
        while True:
            with _client() as client:
                ids = self._list_ids(client, token, baseline)
                if ids:
                    return self._fetch(client, token, ids[0])  # newest
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval_seconds)
