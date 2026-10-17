# API Reference

Base URL (local dev): `http://localhost:8000`

All endpoints except `register`/`login`/`refresh` require a JWT access
token: `Authorization: Bearer <access_token>`. Tokens are issued by
`/api/auth/login/` (15 min access / 7 day refresh, rotation +
blacklist-after-rotation enabled).

## Auth — `apps/users`

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/auth/register/` | `{username, password, email?}` | Runs Django's real password validators (min length 10, common-password check). Throttled `5/min`. |
| POST | `/api/auth/login/` | `{username, password}` | Returns `{access, refresh}`. Throttled `5/min`. |
| POST | `/api/auth/logout/` | `{refresh}` | Blacklists the refresh token. Requires auth. |
| POST | `/api/auth/refresh/` | `{refresh}` | Returns a new `access` token. |
| GET | `/api/me/` | — | Current user profile. |

## Identities — `apps/identities`

Read-only — identities are created internally by the agent
(`identity.create` tool), not directly via the API.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/identities/` | Scoped to the requesting user. |
| GET | `/api/identities/{id}/` | Never includes the password. Cross-user access returns `404` (not `403`), so existence isn't leaked. |

## Registration jobs — `apps/registration`

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/registration-jobs/` | `{url}` | Validates the URL through the real SSRF guard before creating anything. Throttled `10/hour`. Enqueues a Celery task and returns current state (refreshed from DB after dispatch, not a stale snapshot). |
| GET | `/api/registration-jobs/` | — | The user's own jobs. |
| GET | `/api/registration-jobs/{id}/` | — | Includes `steps` (each with a secret-free `detail`, `success`, `error`), plus `provider`/`model` (the AI that handled the job) and `account_id` once completed. |
| POST | `/api/registration-jobs/{id}/resume/` | — | Only valid from `captcha_required`/`human_action_required`. `400` otherwise. |
| POST | `/api/registration-jobs/{id}/cancel/` | — | Only valid for non-terminal jobs. `400` otherwise. |
| POST | `/api/registration-jobs/{id}/retry/` | — | Starts a new job for the same site. Only valid from `failed`/`cancelled`/`expired`; the original stays as a record. Throttled like job creation. |
| DELETE | `/api/registration-jobs/{id}/` | — | Hides a finished or paused job from the dashboard (soft delete). `400` while the job is running. A vault account created by the job is not touched. |
| POST | `/api/registration-jobs/clear-finished/` | — | Hides every failed/cancelled/expired job. Returns `{"cleared": n}`. Completed jobs are kept. |

Job `state` values: `queued`, `starting`, `opening_site`, `analyzing`,
`identity_created`, `filling_form`, `submitting`, `waiting_for_email`,
`verifying`, `completed`, `captcha_required`, `human_action_required`,
`failed`, `cancelled`, `expired`.

## Account vault — `apps/accounts`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/accounts/` | Metadata only — no credentials. |
| GET | `/api/accounts/{id}/` | Metadata only. |
| POST | `/api/accounts/{id}/reveal-credentials/` | Returns the real plaintext password. **Audit-logged** with the requesting IP. `410` if the account was deleted. |
| DELETE | `/api/accounts/{id}/` | Soft-deletes AND scrubs the underlying encrypted secret (not just a status flag). |

## Common error shape

Domain errors return a JSON body with `detail`, and (internally) map to
one of the documented error codes — see `docs/security.md` for the
full taxonomy: `UNSUPPORTED_WEBSITE`, `REGISTRATION_NOT_FOUND`,
`CAPTCHA_REQUIRED`, `HUMAN_ACTION_REQUIRED`, `EMAIL_NOT_RECEIVED`,
`EMAIL_VERIFICATION_FAILED`, `REGISTRATION_FAILED`, `BROWSER_ERROR`,
`AI_ERROR`, `RATE_LIMITED`, `DOMAIN_BLOCKED`, `JOB_EXPIRED`,
`UNSAFE_URL`.

## Ownership model

Every resource is scoped to `request.user`. Detail endpoints filter
their queryset by owner (not just an object-level permission check) so
a non-owner gets a clean `404`, never a `403` that would confirm the
resource exists.


## Live browser view

- `GET /api/registration-jobs/{id}/live/?since=<seq>` — latest screenshot of the agent's browser
  (`{state, interactive, seq, frame: {image(base64 jpeg), width, height, url} | null}`). `frame` is `null`
  when unchanged since `since`. Polling marks a viewer as present so the worker publishes frames.
  `interactive` is true while the job is paused and the browser is waiting for the user.
- `POST /api/registration-jobs/{id}/live/input/` — `{type: click, x, y}` | `{type: type, text, submit?}` |
  `{type: key, key}` | `{type: scroll, dy}`. `409` unless the browser is waiting for input.
- `POST /api/registration-jobs/{id}/resume/` — while the worker still holds the browser this signals it to
  continue in the same browser; otherwise it starts a fresh run as before.

## Settings, saved details and email

- `GET /api/profile/` — `{account_mode, standard_fields, entries}` (entries are decrypted for the owner only).
- `PATCH /api/preferences/` — `{"account_mode": "temporary" | "permanent"}`.
- `PUT /api/profile/entries/{key}/` — `{value, label?}`; an empty value deletes. Keys that look like secrets (password, pin, card number…) are refused. `DELETE` also removes.
- `GET|PUT|DELETE /api/email-connection/` — the user's own mailbox for permanent accounts. `PUT {address, password, host?}` logs in over IMAP (port 993 only, host must resolve to a public address) before saving; the secret is stored encrypted and never returned.
- `POST /api/email-connection/test/` — re-check the saved connection.
- `GET /api/email-connection/gmail/authorize/` → `{url}` (501 if `GOOGLE_OAUTH_*` is not configured); `GET .../gmail/callback/` is Google's redirect target (signed `state`, read-only Gmail scope).

## Questions from the agent

While a job runs the agent can ask for a missing detail. The job moves to `waiting_for_user` and `GET /api/registration-jobs/{id}/` includes `pending_question: {id, key, question, options, sensitive}`.

- `POST /api/registration-jobs/{id}/questions/{qid}/answer/` — `{answer, remember?}` or `{skip: true}`. `remember` saves it as a profile entry under the question's key.

Job fields added: `kind` (`registration` | `form`), `source` (`web` | `mcp`), `account_mode`, `target_url`, `goal`, `result`, `auth_check`. Pasting a Google Form URL (`docs.google.com/forms/...` or `forms.gle/...`) creates a `form` job; its `result.submitted` lists every question and answer that was sent.

## MCP server

`POST /mcp/` with `Authorization: Bearer tia_…` (Streamable HTTP, JSON responses; stateless). Keys: `GET|POST /api/api-keys/`, `DELETE /api/api-keys/{id}/` (the key is shown once; only a hash is stored).

Tools: `register_on_site{url, extraction_goal?, account_mode?}`, `get_job{job_id}`, `list_jobs`, `answer_question{job_id, question_id, answer}`, `cancel_job{job_id}`. Jobs started over MCP must first call the agent's `site.report_auth_methods`; a site with no email + password sign-in ends with `error_code: AUTH_METHOD_UNSUPPORTED` and nothing is created. Passwords are never returned over MCP.
