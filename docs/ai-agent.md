# AI Agent

## Provider abstraction

`ai/base.py` defines `AIProvider` — one method, `complete(messages,
tools) -> CompletionResult`, in provider-agnostic form
(`ai/schemas.py`). `ai/providers/agent_router.py` is the only concrete
implementation right now; `ai/router.py` picks it based on
`settings.AI_PROVIDER`. Adding `OpenAIProvider`/`AnthropicProvider`/
`GoogleProvider` later means adding a new file in `ai/providers/` and
registering it in `ai/router.py` — nothing else in the codebase
imports a provider directly.

**Agent Router's exact wire format is unverified** — see
`docs/security.md`'s known limitations. The implementation assumes
OpenAI-compatible `/chat/completions` tool calling; adjust
`_to_provider_request`/`_from_provider_response` in
`ai/providers/agent_router.py` if your instance differs.

## Tool registry

`apps/ai_agent/tools.py` defines every tool the model can call — 18
tools across four namespaces, matching the original spec's tool list
exactly:

- `browser.open`, `.inspect`, `.click`, `.type`, `.select`, `.scroll`, `.go_back`
- `identity.create`, `.get`
- `email.get_mailbox`, `.list_messages`, `.read_message`, `.wait_for_verification`
- `registration.get_status`, `.mark_complete`, `.mark_failed`, `.mark_captcha_required`, `.mark_human_action_required`

Each has a Pydantic argument schema and a handler wired to the real
Phase 4–6 service code (`apps/identities/service.py`,
`apps/email_service/service.py`, `apps/browser/actions.py`) — not a
parallel reimplementation.

## Dispatcher — the actual security boundary

See `docs/security.md`. Short version: `dispatch_tool_call()` is the
only path from a model's tool call to real code, and it validates
before executing, every time.

## Agent loop

`apps/ai_agent/agent_loop.py::AgentRunner`:

1. Opens a `ManagedBrowserSession` (real Playwright, SSRF-checked navigation).
2. Sends the system prompt + tool definitions + conversation history to the provider.
3. For each tool call the model returns: validate → execute → persist a
   `RegistrationStep` (the full audit trail) → append the result as a
   `tool` message.
4. Repeats until the job reaches a terminal or resumable state, or
   `MAX_AGENT_STEPS`/`MAX_JOB_DURATION_SECONDS` is hit — verified by
   test to actually stop a stalling model rather than loop forever.

## System prompt

`ai/prompts/system_prompt.py` — hard-codes the untrusted-content rules
and the CAPTCHA/security-bypass refusal, verbatim from the original
spec. Read `docs/security.md` for what this guarantees vs. what it
doesn't (structural enforcement vs. model behavior).

## Cost control

`MAX_AGENT_STEPS` (default 30) and `MAX_JOB_DURATION_SECONDS` (default
300) are both configurable via env, both enforced in the loop itself.
`AgentSession` tracks per-job token usage (`total_input_tokens`,
`total_output_tokens`) for cost visibility.
