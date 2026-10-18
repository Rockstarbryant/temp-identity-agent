# Account type, saved details, forms and MCP

**Account type** (Settings): *temporary* uses a generated identity and a disposable mail.tm inbox. *Permanent* uses the
user's real name (if saved), a generated password and their own connected inbox; the identity doesn't expire.
The mode is copied onto each job when it is created.

**Reading the user's inbox** (permanent only): IMAP + app password (any provider; port 993, host checked against the SSRF
rules) or Gmail OAuth (`gmail.readonly`). A job only sees mail that arrives *after it started* (IMAP UID baseline /
Gmail `after:` timestamp), the inbox is opened read-only, and the secret lives in `EmailConnection`, not in each job.
Verification mail that lands in Spam is not read over IMAP (INBOX only).

**Saved details and questions**: `ProfileEntry` rows (encrypted). The agent calls `profile.get` (names first, then only the
keys it needs), and `user.ask` for anything missing. Saved answers are returned without bothering the user. Unsaved ones put
the job in `waiting_for_user` (browser stays open, up to `HUMAN_ASSIST_TIMEOUT_SECONDS`). Passwords are never asked or saved.

**Google Forms**: a pasted form URL becomes a `form` job with its own prompt: read every page, collect missing answers first,
fill, submit, then `form.complete` records each question and answer for the user.

**MCP**: see `docs/api.md`. External clients start jobs and poll them; the web UI link in `get_job` is how a human handles a
CAPTCHA or answers a question.

**Privacy note**: any value the agent uses to fill a form passes through the configured LLM provider. Free OpenRouter models
may log prompts, so keep especially sensitive details (e.g. national ID) out of the saved list if that matters to you.

## Accounts for forms that need a sign-in

Some Google and Microsoft forms only accept signed-in people. Under Settings, "Accounts for forms that need a sign-in", a user can give the agent a **separate account made just for this** (never their main one).

- The password (optional) and the browser session (cookies) are stored encrypted (`ConnectedAccount`). They are never sent to the AI model: `account.sign_in` types the password into the page from server code.
- "Sign in now" starts an `account_setup` job (no AI): it opens the provider's sign-in page, types the email and password, and if anything more is asked (2-step verification, "verify it's you", "browser not secure") it pauses and shows the live browser so the user finishes the sign-in. The session is then saved.
- Later form jobs load that session into their own browser. If the form still shows a sign-in page, the agent calls `account.sign_in`; if that needs the user, the job pauses for the live view as it does for CAPTCHAs.
- Sessions are per user and per provider and are loaded only into that user's own job browser; every job starts a fresh browser context.

API: `GET/PUT /api/connected-accounts/`, `DELETE /api/connected-accounts/{provider}/`, `POST /api/connected-accounts/{provider}/signin/`.
