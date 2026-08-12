"""
Playwright browser session management.

Runs in a Celery worker, never inline in a Django request/response
cycle (see architecture.md — long-running browser work must not block
HTTP). Every navigation goes through apps.common.url_safety.validate_url
first, including redirect targets, per the project's SSRF requirements.
"""
import os
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from apps.browser.models import BrowserSession
from apps.common.exceptions import BrowserError
from apps.common.url_safety import validate_url
from apps.registration.models import RegistrationJob

SCREENSHOT_DIR = Path(getattr(settings, "BASE_DIR", ".")) / "media" / "screenshots"


class ManagedBrowserSession:
    """
    Context manager wrapping one Playwright browser + page, mirrored to
    a BrowserSession row for status/audit purposes.

    Usage:
        with ManagedBrowserSession(job) as session:
            session.goto("https://example.com/register")
            snapshot = session.inspect()
            ...
    """

    def __init__(self, job: RegistrationJob, headless: bool = True):
        self.job = job
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.page: Page | None = None
        self.db_session: BrowserSession | None = None

    def __enter__(self) -> "ManagedBrowserSession":
        self.db_session, _ = BrowserSession.objects.get_or_create(
            job=self.job, defaults={"status": BrowserSession.Status.OPEN}
        )
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self.page = self._browser.new_page()
        except Exception as exc:  # Playwright raises its own exception types
            self.db_session.status = BrowserSession.Status.CRASHED
            self.db_session.save(update_fields=["status", "updated_at"])
            raise BrowserError(f"Failed to launch browser: {exc}") from exc
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._browser is not None:
                self._browser.close()
            if self._playwright is not None:
                self._playwright.stop()
        finally:
            if self.db_session is not None:
                self.db_session.status = (
                    BrowserSession.Status.CRASHED if exc_type else BrowserSession.Status.CLOSED
                )
                self.db_session.ended_at = timezone.now()
                self.db_session.save(update_fields=["status", "ended_at", "updated_at"])
        # Don't suppress exceptions — let the caller's error handling see them.
        return False

    def goto(self, url: str) -> None:
        validate_url(url)
        try:
            response = self.page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:
            raise BrowserError(f"Navigation to {url!r} failed: {exc}") from exc

        # Re-validate the URL we actually landed on — a redirect chain
        # can end somewhere different from what was requested.
        validate_url(self.page.url)

        if response is not None and response.status >= 400:
            raise BrowserError(f"Navigation to {url!r} returned HTTP {response.status}.")

    def screenshot(self, name: str) -> str:
        """Save a screenshot and return its path (relative, stored on RegistrationStep)."""
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{self.job.id}_{name}.png"
        full_path = SCREENSHOT_DIR / filename
        self.page.screenshot(path=str(full_path))
        return str(full_path)
