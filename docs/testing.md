# Testing

## Automated suite

`cd backend && python -m pytest` — 75 tests, one `tests/` package per
app. Confirmed stable across repeated runs (not flaky).

| Area | File | Covers |
|---|---|---|
| Security utilities | `apps/common/tests/test_security.py` | Encryption round-trip + tamper rejection, SSRF rejection (localhost/private/link-local/metadata IPs, unresolvable hosts), safe-URL acceptance |
| Auth | `apps/users/tests/test_auth.py` | Register/weak-password/duplicate-username, login/logout/blacklist, `/api/me/` |
| Identities | `apps/identities/tests/test_identities.py` | Password policy + collision-freedom, ownership enforcement, API scoping, 404-not-403 |
| Email | `apps/email_service/tests/test_email_service.py` | Extraction (link scoring, OTP proximity, malicious-HTML safety), mail.tm schema contract |
| Browser | `apps/browser/tests/test_browser.py` | Schema parsing, action-layer Playwright call contracts, stale-element handling |
| AI agent | `apps/ai_agent/tests/test_agent.py` | Tool registry validity, **dispatcher security boundary**, full agent-loop happy path, CAPTCHA pause, step-budget cutoff, structural prompt-injection inertness, Agent Router response parsing |
| Orchestration | `apps/registration/tests/test_orchestration.py` | Domain policy (blocked/human/default-allow), concurrency + daily quota limits, full job API flow, ownership, resume/cancel guards |
| Vault | `apps/accounts/tests/test_vault.py` | List/detail never leak passwords, reveal is audit-logged, cross-user denial, delete actually scrubs secrets |

## Local mock registration sites

`backend/tests/fixtures/mock_sites/` — six fixtures, matching the
original spec's list exactly: simple registration, registration +
email verification, multi-step (2 pages), failing registration,
CAPTCHA requiring human intervention, and unexpected page structure.
Served standalone via `backend/tests/fixtures/serve_mock_sites.py` —
deliberately outside the Django app, since these are static fixtures
for the *browser layer* to navigate to, not application data.

**Never test against live production websites** — this was a hard
requirement in the original spec, and it's honored throughout: every
test that touches "a website" uses one of these fixtures or a
`MockTransport`/mocked session, never `requests.get("https://some-real-signup-page")`.

## What's genuinely verified vs. structurally reasoned about

Real, executed verification:
- The actual page-inspection JS (Phase 6) run against real parsed DOM
  (Node + `jsdom`) for all 6 fixtures — zero crashes, correct label
  extraction, hidden-field exclusion confirmed, and — notably — the
  prompt-injection probe text in `unexpected_structure.html` **never
  appears in the structured output at all**.
- The mail.tm provider's parsing against fixtures matching their own
  documented schema (not fabricated).
- A full cross-process integration pass: real separate Django + Next.js
  dev servers, real `curl` calls (not the in-process Django test
  client) confirming CORS, JWT issuance, authenticated requests, and
  SSRF rejection all work over an actual network round-trip.
- The full agent loop, including the two safety-critical paths
  (CAPTCHA pause, step-budget cutoff) with a scripted mock AI provider.

Structural reasoning, not live execution (disclosed, not hidden):
- **No live Chromium** in this sandbox — Playwright's CDN isn't in the
  network allowlist. Browser action tests mock the Playwright API
  surface to verify calling contracts; they don't prove real-page
  click/type/screenshot behavior. Verify this first in your own
  environment (`docs/browser-automation.md`).
- **No live Agent Router or mail.tm network access** — provider tests
  verify request/response transformation against realistic or
  documented shapes, not an actual live call.
- **No Docker daemon** — Dockerfile/compose correctness verified via
  real parsers and path checks, not an actual `docker build`.
- **Prompt-injection resistance is only automatable at the structural
  level** (no code-execution tool, validated arguments, tool-result
  content can't itself trigger execution). Whether a live model
  actually follows the system prompt's refusal instructions when
  reading real injected text is a live-LLM behavioral property no unit
  test can certify — this is stated plainly rather than papered over
  with a test that would only prove the mock providers do what they
  were told to do.
