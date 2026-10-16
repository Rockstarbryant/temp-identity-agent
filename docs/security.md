# Security

## Threat model

| Threat | Mitigation | Where |
|---|---|---|
| SSRF via user-submitted URL | Blocks localhost/private/link-local/cloud-metadata IPs; resolves DNS and re-checks; re-validated on every redirect hop and again before every Playwright navigation | `apps/common/url_safety.py`, `apps/browser/playwright_client.py` |
| Credential exposure at rest | Fernet authenticated encryption for identity passwords + mailbox credentials; key from env only, never committed | `apps/common/encryption.py` |
| IDOR / cross-user access | Every detail queryset filtered by owner (not just a permission check) — non-owner gets `404`, not `403` | `apps/common/permissions.py`, every `views.py` |
| Prompt injection from target sites/emails | System prompt hard-codes untrusted-content rules; **structurally** enforced too — no code-execution tool exists, every tool call is Pydantic-validated, hidden/invisible page content never reaches the agent's structured view (confirmed via real DOM tests, see `docs/testing.md`) | `ai/prompts/system_prompt.py`, `apps/ai_agent/dispatcher.py`, `apps/browser/page_inspector.py` |
| CAPTCHA/security-check bypass | Never attempted — the agent's tool set has no bypass capability; it can only call `registration.mark_captcha_required`/`mark_human_action_required` and stop | `apps/ai_agent/tools.py` |
| Malformed/hallucinated tool calls | Every call validated against a Pydantic schema before touching application code; unknown tool names and bad arguments return structured errors, never crash | `apps/ai_agent/dispatcher.py` |
| Unbounded agent cost/runtime | `MAX_AGENT_STEPS` and `MAX_JOB_DURATION_SECONDS`, enforced in the loop itself, not left to model judgment — verified: a stalling model gets cut off, not left running | `apps/ai_agent/agent_loop.py` |
| Credential-stuffing / brute force | Dedicated `auth` throttle scope (5/min), separate from general API limits | `config/settings/base.py` |
| Abuse via job flooding | Per-user concurrency cap (`MAX_CONCURRENT_JOBS`) and daily quota (`MAX_JOBS_PER_USER_PER_DAY`), plus a dedicated `registration_jobs` throttle (10/hour) | `apps/registration/orchestration.py` |
| Stale/leaked secrets past retention | Periodic Celery task scrubs (not just flags) expired identity passwords and mailbox credentials; manual account delete does the same | `apps/identities/tasks.py`, `apps/accounts/views.py` |
| Sensitive data in logs | Structured JSON logging; passwords/tokens/API keys never logged (nothing in the codebase logs `encrypted_password`, `get_password()`, or the mailbox JWT) | `config/settings/base.py` (`LOGGING`) |

## The AI security boundary, precisely

The model can **only** reach real code through `TOOL_REGISTRY`
(`apps/ai_agent/tools.py`), and every call goes through
`dispatch_tool_call()` (`apps/ai_agent/dispatcher.py`), which:

1. Rejects any tool name not in the registry.
2. Validates arguments against that tool's Pydantic schema — rejects
   missing/wrong-typed/oversized fields.
3. Catches every exception the handler can raise and returns a
   structured `{"success": false, "error": ...}` instead of ever
   letting a tool crash the loop.

There is no "run arbitrary code" or "run arbitrary JS" tool, by
design — not because the system prompt asks the model not to use one,
but because it doesn't exist in the registry at all.

**What this guarantees vs. what it doesn't**: the structural tests
(`apps/ai_agent/tests/test_agent.py::TestDispatcherSecurity`) prove
the boundary holds regardless of what the model tries to call. They
do **not** prove a live model will always recognize and refuse an
injected instruction in the first place — that's a live-LLM behavioral
property, outside what an automated test suite can certify. The
system prompt's untrusted-content rules are the mitigation for that
half of the problem; the dispatcher is the mitigation for the other
half (what happens even if the model is fooled).

## Known limitations (disclosed, not hidden)

- **LLM providers are verified against mocked HTTP only.** OpenRouter and
  Groq are exercised via mocked `/chat/completions` responses in tests, not
  live calls. `openrouter/free` routes to whichever free model is available,
  so model behaviour (and which third party sees the page content sent to
  the agent) can vary between calls.
- **mail.tm and Playwright integrations are verified against
  documented schemas / jsdom-simulated DOM, not live network calls or
  a real browser** — this sandbox's network/tooling couldn't reach
  either. See `scripts/live_smoke_test_mailtm.py` and the Docker
  image's `playwright install --with-deps` for how to verify live.
- **Resume closes the browser session** rather than keeping it alive
  across an arbitrarily long human-response window — see
  `docs/architecture.md`'s "Resume model" section.
- **Docker images are unverified by an actual `docker build`** — this
  sandbox has no Docker daemon. Dockerfile/compose syntax and every
  `COPY` source path were verified with real parsers, but the build
  itself hasn't run. See `docs/deployment.md`.
