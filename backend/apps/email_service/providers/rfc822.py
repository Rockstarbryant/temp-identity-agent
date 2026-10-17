"""Parse a raw RFC 822 message (what IMAP and the Gmail API return) into our MessageDetail."""
from email import message_from_bytes, policy
from email.utils import parsedate_to_datetime

from apps.email_service.schemas import MessageDetail


def _body(msg, kind: str) -> str:
    part = msg.get_body(preferencelist=(kind,))
    if part is None:
        return ""
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def parse_rfc822(raw: bytes, external_id: str) -> MessageDetail:
    msg = message_from_bytes(raw, policy=policy.default)
    received = None
    if msg["Date"]:
        try:
            received = parsedate_to_datetime(str(msg["Date"]))
        except (TypeError, ValueError):
            received = None
    return MessageDetail(
        external_id=external_id,
        sender=str(msg["From"] or "")[:255],
        subject=str(msg["Subject"] or "")[:500],
        text_body=_body(msg, "plain"),
        html_body=_body(msg, "html"),
        received_at=received,
    )
