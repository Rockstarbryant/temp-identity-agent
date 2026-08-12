# Email Service

## Provider abstraction

`apps/email_service/providers/base.py::EmailProvider` — `create_mailbox`,
`get_messages`, `get_message`, `wait_for_message`, plus shared default
implementations of `extract_verification_link`/`extract_otp`.
`apps/email_service/service.py::get_provider()` picks a concrete
implementation via `settings.EMAIL_PROVIDER`.

## mail.tm — the current implementation

`apps/email_service/providers/mailtm.py`. No API key required —
JWT-based: `GET /domains` → `POST /accounts` → `POST /token` → poll
`GET /messages` / `GET /messages/{id}`.

One real-world gotcha handled explicitly: **mail.tm returns `html` as
a list of HTML fragments, not a string** — the provider joins them
before handing off to extraction.

## Extraction

`apps/email_service/extraction.py`:

- **Verification links**: every `href` (or bare URL in plaintext) is
  scored by how many verification-related keywords appear in the URL
  itself; falls back to the first link found if nothing scores above
  zero. Not just "first link" — tested against realistic multi-link
  emails (account settings / verify / unsubscribe all present) to
  confirm the right one wins.
- **OTP codes**: prefers a digit run near a code-related keyword
  (`code`, `otp`, `pin`, `passcode`); falls back to the first
  standalone 4–8 digit run otherwise.

## Persistence layer

`apps/email_service/service.py`:

- `create_mailbox_for_identity()` — provisions via the provider,
  persists a `TemporaryEmail` row (credential encrypted), and
  back-fills `identity.email`.
- `sync_messages()` — idempotent upsert (`update_or_create` keyed on
  `mailbox` + `external_id`) — verified: re-syncing doesn't create
  duplicate rows.
- `wait_for_verification_email()` — blocks (via provider polling) until
  a message arrives or times out.

## Testing caveats (disclosed)

This sandbox's network egress doesn't include `api.mail.tm`, so the
provider was verified against **mail.tm's own documented response
schema** via `httpx.MockTransport` fixtures (not fabricated — taken
from their docs), not a live call. Run
`python scripts/live_smoke_test_mailtm.py` yourself to confirm the
live endpoint behaves as documented before relying on it in
production.

## Swapping providers later

Implement a new `EmailProvider` subclass, register it in
`apps/email_service/service._PROVIDERS`, and point `EMAIL_PROVIDER` at
it. No other code changes — `create_mailbox_for_identity`/
`sync_messages`/`wait_for_verification_email` are provider-agnostic.
