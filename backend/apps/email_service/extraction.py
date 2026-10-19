"""
Extraction of verification links and OTP codes from email content.

Heuristic, not perfect — target sites vary a lot. Verification links are
scored by how strongly their URL or surrounding anchor text signals
"this is the confirm/verify link" versus being scored on position alone.
OTP codes are found by proximity to code-related keywords first, falling
back to the first standalone 4-8 digit run if no keyword match exists.
"""
import html
import re

_LINK_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_BARE_URL_RE = re.compile(r'https?://[^\s<>"\')]+')

_VERIFY_KEYWORDS = (
    "verify", "confirm", "activate", "activation", "validate",
    "verification", "confirmation", "authenticate",
)

_NOT_A_LINK_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".ico", ".webp")
_NEVER_VERIFY = ("unsubscribe", "optout", "opt-out", "preferences", "privacy", "terms")

_OTP_KEYWORD_RE = re.compile(
    r"(?:code|otp|pin|passcode)\D{0,20}(\d{4,8})", re.IGNORECASE
)
_STANDALONE_DIGITS_RE = re.compile(r"\b(\d{4,8})\b")


def find_verification_link(html_or_text: str) -> str | None:
    """
    Find the most likely email-verification link in a message body.

    Strategy: collect every href (or bare URL if the body is plaintext),
    score each by whether the URL itself or nearby text contains a
    verification keyword, and return the highest-scoring candidate.
    Falls back to the first URL found if nothing scores above zero.
    """
    if not html_or_text:
        return None

    candidates: list[tuple[str, int]] = []

    hrefs = _LINK_RE.findall(html_or_text)
    urls = hrefs if hrefs else _BARE_URL_RE.findall(html_or_text)

    for raw in urls:
        url = html.unescape(raw).strip()  # href="...?a=1&amp;b=2" must become ...?a=1&b=2
        lowered = url.lower()
        if not lowered.startswith(("http://", "https://")) or lowered.endswith(_NOT_A_LINK_SUFFIXES):
            continue  # mailto:, tel:, images, stylesheets
        score = sum(1 for kw in _VERIFY_KEYWORDS if kw in lowered)
        if any(word in lowered for word in _NEVER_VERIFY):
            score -= 5  # unsubscribe / preference links are never the one we want
        candidates.append((url, score))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[1], reverse=True)  # stable: ties keep email order
    return candidates[0][0]


def find_otp_code(text: str) -> str | None:
    """
    Find a one-time-passcode / verification code in message text.

    Prefers a digit run that appears near a code-related keyword; falls
    back to the first standalone 4-8 digit run otherwise (best-effort —
    plenty of false-positive risk with dates/amounts, which is why the
    keyword-proximity match is tried first).
    """
    if not text:
        return None

    keyword_match = _OTP_KEYWORD_RE.search(text)
    if keyword_match:
        return keyword_match.group(1)

    standalone_match = _STANDALONE_DIGITS_RE.search(text)
    if standalone_match:
        return standalone_match.group(1)

    return None
