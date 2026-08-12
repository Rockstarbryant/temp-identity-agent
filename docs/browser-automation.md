# Browser Automation

## Runs in Celery, never inline in a request

`ManagedBrowserSession` (`apps/browser/playwright_client.py`) is a
context manager wrapping one Playwright browser + page, mirrored to a
`BrowserSession` DB row. It's only ever instantiated from
`AgentRunner.run()`, which itself only ever runs inside a Celery task.

## Page inspection: DOM → structured JSON

`apps/browser/page_inspector.py` runs a single in-page JS scan
(`page.evaluate`) that:

- Selects every `input:not([type=hidden])`, `select`, `textarea`,
  `button`, `a[href]`, `[role=button]`.
- Tags each with a stable `data-tia-id` attribute so later actions
  address exactly the element the agent reasoned about.
- Extracts a best-effort label: explicit `<label for>`, `aria-label`,
  wrapping `<label>` (with nested form-control text stripped out —
  see below), `placeholder`, then the element's own text.
- Reports visibility via real bounding-box + computed-style checks
  (only meaningful in an actual browser — see testing caveats below).

The agent reasons over the resulting `PageSnapshot`/`PageElement`
objects (`apps/browser/schemas.py`) — never raw HTML.

### Two real bugs found and fixed while building this (see commit history / prior phase write-ups)

1. `innerText` can be `undefined` on some nodes — unguarded access
   crashed the scan. Fixed with optional chaining.
2. A `<label>` wrapping a `<select>` picked up the select's own option
   text (`"Country United States Canada"` instead of `"Country"`) —
   fixed by cloning the label node and stripping nested form controls
   before reading its text.

## Allowlisted actions

`apps/browser/actions.py` — `browser_open`, `_inspect`, `_click`,
`_type`, `_select`, `_scroll`, `_go_back`. This is the **entire**
surface exposed to the agent; there is no arbitrary-selector or
arbitrary-JS action. Every action addresses elements by `element_id`
from the most recent inspection — a stale/hallucinated id raises
`BrowserError` rather than silently failing or falling back to a guess.

## SSRF protection applied here specifically

Every `.goto()` call validates the target URL through
`apps/common/url_safety.validate_url()` — **and re-validates the URL
actually landed on**, since a redirect chain can end somewhere
different from what was requested.

## Testing caveats (disclosed)

This sandbox has no Playwright browser binary (its CDN isn't in the
network allowlist here), so the inspection JS was verified via Node +
`jsdom` against real parsed DOM trees — not a live Chromium instance.
`jsdom` doesn't compute layout, so `isVisible()`'s bounding-box checks
report everything as invisible in that harness; they're only
meaningful once run against a real rendering engine. The Docker image
runs `playwright install --with-deps chromium`, so this becomes fully
testable the moment the stack is actually deployed — verify this
early, since it's the piece with the least ability to be checked here.
