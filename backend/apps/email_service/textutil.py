"""Turning stored email bodies into safe plain text and a list of links. Never returns HTML."""
import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_RE = re.compile(r"</?(?:p|div|br|tr|li|h[1-6]|table|ul|ol)\b[^>]*>", re.IGNORECASE)
_STYLE_RE = re.compile(r"<(script|style|head)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+')
_SPACES_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKS_RE = re.compile(r"\n{3,}")

MAX_TEXT = 20000


def plain_text(text_body: str, html_body: str, limit: int = MAX_TEXT) -> str:
    """The message as plain text: the text part if there is one, else the HTML with tags removed."""
    body = (text_body or "").strip()
    if not body and html_body:
        stripped = _STYLE_RE.sub(" ", html_body)
        stripped = _BLOCK_RE.sub("\n", stripped)
        stripped = _TAG_RE.sub("", stripped)
        body = html.unescape(stripped)
    body = _SPACES_RE.sub(" ", body)
    body = "\n".join(line.strip() for line in body.splitlines())
    return _BLANKS_RE.sub("\n\n", body).strip()[:limit]


def snippet(text_body: str, html_body: str, length: int = 140) -> str:
    return " ".join(plain_text(text_body, html_body, 600).split())[:length]


def all_links(text_body: str, html_body: str, limit: int = 15) -> list[str]:
    """Distinct http(s) links in the message (decoded), in order of appearance."""
    found: list[str] = []
    for raw in _HREF_RE.findall(html_body or "") + _URL_RE.findall(text_body or "") + _URL_RE.findall(html_body or ""):
        url = html.unescape(raw).strip()
        if url.lower().startswith(("http://", "https://")) and url not in found:
            found.append(url)
        if len(found) >= limit:
            break
    return found
