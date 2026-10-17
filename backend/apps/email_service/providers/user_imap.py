"""
Reads the user's own mailbox over IMAP (any provider that offers IMAP + an app password).

Privacy: the agent only ever sees messages that arrived AFTER the job started
(`baseline_uid`), never the user's existing inbox. The mailbox is opened read-only.

The credential string is JSON: {"connection_id": "...", "baseline_uid": 123}. The
password stays in the EmailConnection row, not copied into each job's mailbox.
"""
import imaplib
import json
import ssl
import time

from apps.email_service.providers.base import EmailProvider, EmailProviderError
from apps.email_service.providers.rfc822 import parse_rfc822
from apps.email_service.schemas import MessageDetail, MessageSummary, ProvisionedMailbox

IMAP_TIMEOUT = 20
MAX_LISTED = 10

# Hosts we can fill in for the user from their address.
IMAP_PRESETS = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com",
    "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com",
    "yahoo.com": "imap.mail.yahoo.com",
    "icloud.com": "imap.mail.me.com",
    "me.com": "imap.mail.me.com",
    "zoho.com": "imap.zoho.com",
    "aol.com": "imap.aol.com",
}


def preset_host(address: str) -> str:
    return IMAP_PRESETS.get(address.rsplit("@", 1)[-1].lower(), "")


def open_imap(host: str, port: int, address: str, password: str) -> imaplib.IMAP4_SSL:
    """Log in over TLS. Raises EmailProviderError with a user-presentable message."""
    try:
        conn = imaplib.IMAP4_SSL(host, port, timeout=IMAP_TIMEOUT, ssl_context=ssl.create_default_context())
    except (OSError, imaplib.IMAP4.error) as exc:
        raise EmailProviderError(f"Could not reach {host}: {exc}") from exc
    try:
        conn.login(address, password)
    except imaplib.IMAP4.error as exc:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001
            pass
        raise EmailProviderError(
            "The mail server rejected the login. For Gmail and most providers you need an "
            "app password, not your normal password."
        ) from exc
    return conn


def current_uid_baseline(conn: imaplib.IMAP4_SSL) -> int:
    """Highest UID in INBOX right now (0 if empty)."""
    status, data = conn.status("INBOX", "(UIDNEXT)")
    if status != "OK" or not data:
        raise EmailProviderError("Could not read the inbox state.")
    text = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
    marker = "UIDNEXT"
    try:
        nxt = int(text.split(marker, 1)[1].strip(" )").split()[0].strip(")"))
    except (IndexError, ValueError) as exc:
        raise EmailProviderError("Could not parse the inbox state.") from exc
    return max(nxt - 1, 0)


class ImapUserMailboxProvider(EmailProvider):
    name = "imap"

    def create_mailbox(self, local_part=None) -> ProvisionedMailbox:  # pragma: no cover - not applicable
        raise EmailProviderError("IMAP mailboxes are connected by the user, not created.")

    # -- helpers --------------------------------------------------------------

    def _connection(self, credential: str):
        from apps.profiles.models import EmailConnection

        info = json.loads(credential)
        try:
            conn = EmailConnection.objects.get(id=info["connection_id"])
        except EmailConnection.DoesNotExist as exc:
            raise EmailProviderError("The connected mailbox was removed in Settings.") from exc
        imap = open_imap(conn.imap_host, conn.imap_port, conn.address, conn.get_secret())
        imap.select("INBOX", readonly=True)
        return imap, int(info.get("baseline_uid", 0))

    def _new_uids(self, imap, baseline: int) -> list[int]:
        status, data = imap.uid("SEARCH", None, f"UID {baseline + 1}:*")
        if status != "OK" or not data or not data[0]:
            return []
        # "N:*" always includes the last message even when its UID <= N, so filter.
        return sorted(int(u) for u in data[0].split() if int(u) > baseline)[-MAX_LISTED:]

    def _fetch(self, imap, uid: int) -> MessageDetail:
        status, data = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            raise EmailProviderError(f"Could not fetch message {uid}.")
        return parse_rfc822(data[0][1], str(uid))

    # -- EmailProvider --------------------------------------------------------

    def get_messages(self, credential: str) -> list[MessageSummary]:
        imap, baseline = self._connection(credential)
        try:
            out = []
            for uid in self._new_uids(imap, baseline):
                detail = self._fetch(imap, uid)
                out.append(MessageSummary(
                    external_id=detail.external_id, sender=detail.sender,
                    subject=detail.subject, received_at=detail.received_at,
                ))
            return out
        finally:
            _close(imap)

    def get_message(self, credential: str, external_id: str) -> MessageDetail:
        imap, baseline = self._connection(credential)
        try:
            uid = int(external_id)
            if uid <= baseline:
                raise EmailProviderError("That message arrived before this job started.")
            return self._fetch(imap, uid)
        finally:
            _close(imap)

    def wait_for_message(self, credential, timeout_seconds=60, poll_interval_seconds=4.0):
        deadline = time.monotonic() + timeout_seconds
        while True:
            imap, baseline = self._connection(credential)
            try:
                uids = self._new_uids(imap, baseline)
                if uids:
                    return self._fetch(imap, uids[-1])  # newest
            finally:
                _close(imap)
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval_seconds)


def _close(imap) -> None:
    try:
        imap.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        imap.logout()
    except Exception:  # noqa: BLE001
        pass
