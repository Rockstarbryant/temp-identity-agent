"""
Signing in to a Google / Microsoft account in the agent's browser.

The password is read from the user's ConnectedAccount and typed straight into the
page by this code; it is never given to the AI model. When Google or Microsoft ask
for anything beyond email + password (2-step verification, "verify it's you", a
CAPTCHA, a "browser not secure" refusal), we stop and hand the browser to the user
through the live view instead of trying to get around it.
"""
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from django.utils import timezone

from apps.profiles.models import ConnectedAccount

logger = logging.getLogger("apps.profiles")

LOGIN_HOSTS = {
    "google": {"accounts.google.com"},
    "microsoft": {"login.microsoftonline.com", "login.live.com", "login.microsoft.com"},
}
LOGIN_URLS = {
    "google": "https://accounts.google.com/ServiceLogin",
    "microsoft": "https://login.live.com/",
}
_GOOGLE_HOSTS = {"docs.google.com", "forms.gle", "accounts.google.com", "drive.google.com", "forms.google.com"}
_MICROSOFT_HOSTS = {"forms.cloud.microsoft", "forms.office.com", "forms.microsoft.com", "login.microsoftonline.com",
                    "login.live.com", "login.microsoft.com", "office.com", "www.office.com"}


def provider_for_url(url: str) -> str:
    """"google" / "microsoft" for pages that sign in with those accounts, else ""."""
    host = (urlparse(url or "").hostname or "").lower()
    if host in _GOOGLE_HOSTS or host.endswith(".google.com"):
        return "google"
    if host in _MICROSOFT_HOSTS or host.endswith((".office.com", ".microsoft.com", ".cloud.microsoft")):
        return "microsoft"
    return ""


def is_login_url(provider: str, url: str) -> bool:
    return (urlparse(url or "").hostname or "").lower() in LOGIN_HOSTS.get(provider, set())


@dataclass
class LoginResult:
    ok: bool
    needs_human: bool = False
    reason: str = ""


def _visible(page, selector: str, timeout_ms: int = 8000):
    loc = page.locator(selector).first
    try:
        loc.wait_for(state="visible", timeout=timeout_ms)
        return loc
    except Exception:  # noqa: BLE001 - timeout => not there
        return None


def _left_login(page, provider: str, timeout_ms: int) -> bool:
    try:
        page.wait_for_url(lambda u: not is_login_url(provider, u), timeout=timeout_ms)
        return True
    except Exception:  # noqa: BLE001
        return False


def _stuck_reason(page, provider: str) -> str:
    name = "Google" if provider == "google" else "Microsoft"
    try:
        text = (page.inner_text("body", timeout=3000) or "").lower()
    except Exception:  # noqa: BLE001
        text = ""
    if "not secure" in text or ("try again" in text and "couldn" in text):
        return f"{name} refused the automatic sign-in. Please sign in yourself in the browser below."
    if "wrong password" in text or "incorrect" in text or "password is incorrect" in text:
        return f"{name} says the saved password is wrong. Please sign in yourself, and update the password in Settings."
    return f"{name} needs an extra check (for example a verification code). Please finish signing in below."


def _google_login(page, email: str, password: str) -> LoginResult:
    # "Choose an account" screen: pick "Use another account" if present.
    box = _visible(page, 'input[type="email"]', 8000)
    if box is None:
        return LoginResult(False, True, _stuck_reason(page, "google"))
    box.fill(email)
    box.press("Enter")
    pw = _visible(page, 'input[type="password"]', 15000)
    if pw is None:
        return LoginResult(False, True, _stuck_reason(page, "google"))
    if not password:
        return LoginResult(False, True, "Enter your Google password in the browser below.")
    pw.fill(password)
    pw.press("Enter")
    if _left_login(page, "google", 25000):
        return LoginResult(True)
    return LoginResult(False, True, _stuck_reason(page, "google"))


def _microsoft_login(page, email: str, password: str) -> LoginResult:
    box = _visible(page, 'input[name="loginfmt"], input[type="email"]', 10000)
    if box is None:
        return LoginResult(False, True, _stuck_reason(page, "microsoft"))
    box.fill(email)
    box.press("Enter")
    pw = _visible(page, 'input[name="passwd"], input[type="password"]', 15000)
    if pw is None:
        return LoginResult(False, True, _stuck_reason(page, "microsoft"))
    if not password:
        return LoginResult(False, True, "Enter your Microsoft password in the browser below.")
    pw.fill(password)
    pw.press("Enter")
    # "Stay signed in?" -> Yes keeps the session alive for the next job.
    stay = _visible(page, "#idSIButton9", 6000)
    if stay is not None:
        try:
            if "stay signed in" in (page.inner_text("body", timeout=3000) or "").lower():
                stay.click()
        except Exception:  # noqa: BLE001
            pass
    if _left_login(page, "microsoft", 25000):
        return LoginResult(True)
    return LoginResult(False, True, _stuck_reason(page, "microsoft"))


def perform_login(page, account: ConnectedAccount) -> LoginResult:
    """Sign in on the page that is currently showing the provider's login screen."""
    try:
        password = account.get_password()
    except Exception:  # noqa: BLE001 - key rotated / corrupt
        password = ""
    try:
        if account.provider == "google":
            return _google_login(page, account.email, password)
        return _microsoft_login(page, account.email, password)
    except Exception as exc:  # noqa: BLE001 - never crash a job over a login page
        logger.warning("Sign-in attempt failed for %s: %s", account.provider, exc)
        return LoginResult(False, True, "Couldn't sign in automatically. Please sign in yourself in the browser below.")


# -- saved sessions ---------------------------------------------------------------

def get_account(user, provider: str) -> ConnectedAccount | None:
    if not provider:
        return None
    return ConnectedAccount.objects.filter(user=user, provider=provider).first()


def save_session(account: ConnectedAccount, browser_session) -> bool:
    """Store the browser's cookies on the account (encrypted). Returns True if saved."""
    state = browser_session.export_storage_state()
    if not state or not state.get("cookies"):
        return False
    account.set_session(state)
    account.last_used_at = timezone.now()
    account.last_error = ""
    account.save(update_fields=["encrypted_session", "session_saved_at", "last_used_at", "last_error", "updated_at"])
    return True
