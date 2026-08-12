"""
Allowlisted browser actions.

This is the ENTIRE surface the AI agent is permitted to act through —
Phase 7's tool-calling layer maps `browser.click`, `browser.type`, etc.
directly onto these functions and nothing else. There is no
"run arbitrary JS" or "execute Python" action here by design: see
architecture.md section 6 (AI security requirement) and section 7.

Every action addresses elements by the `element_id` assigned during
the most recent inspect_page() call (the `data-tia-id` attribute),
never by raw CSS/XPath supplied by the model — this keeps the agent
constrained to elements it has actually seen and reasoned about.
"""
from apps.browser.page_inspector import inspect_page
from apps.browser.playwright_client import ManagedBrowserSession
from apps.browser.schemas import BrowserActionResult
from apps.common.exceptions import BrowserError

_SELECTOR = '[data-tia-id="{element_id}"]'


def _locator(session: ManagedBrowserSession, element_id: str):
    locator = session.page.locator(_SELECTOR.format(element_id=element_id))
    if locator.count() == 0:
        raise BrowserError(
            f"element_id {element_id!r} not found — it may belong to a stale "
            "snapshot. Call browser.inspect again before acting."
        )
    return locator.first


def browser_open(session: ManagedBrowserSession, url: str) -> BrowserActionResult:
    session.goto(url)
    snapshot = inspect_page(session.page)
    return BrowserActionResult(success=True, message=f"Opened {url}", snapshot=snapshot)


def browser_inspect(session: ManagedBrowserSession) -> BrowserActionResult:
    snapshot = inspect_page(session.page)
    return BrowserActionResult(success=True, snapshot=snapshot)


def browser_click(session: ManagedBrowserSession, element_id: str) -> BrowserActionResult:
    locator = _locator(session, element_id)
    locator.click()
    snapshot = inspect_page(session.page)
    return BrowserActionResult(success=True, message=f"Clicked {element_id}", snapshot=snapshot)


def browser_type(session: ManagedBrowserSession, element_id: str, text: str) -> BrowserActionResult:
    locator = _locator(session, element_id)
    locator.fill(text)
    snapshot = inspect_page(session.page)
    return BrowserActionResult(success=True, message=f"Typed into {element_id}", snapshot=snapshot)


def browser_select(session: ManagedBrowserSession, element_id: str, value: str) -> BrowserActionResult:
    locator = _locator(session, element_id)
    locator.select_option(value)
    snapshot = inspect_page(session.page)
    return BrowserActionResult(success=True, message=f"Selected {value!r} in {element_id}", snapshot=snapshot)


def browser_scroll(session: ManagedBrowserSession, direction: str = "down") -> BrowserActionResult:
    delta = 800 if direction == "down" else -800
    session.page.mouse.wheel(0, delta)
    snapshot = inspect_page(session.page)
    return BrowserActionResult(success=True, message=f"Scrolled {direction}", snapshot=snapshot)


def browser_go_back(session: ManagedBrowserSession) -> BrowserActionResult:
    session.page.go_back(wait_until="domcontentloaded")
    snapshot = inspect_page(session.page)
    return BrowserActionResult(success=True, message="Navigated back", snapshot=snapshot)
