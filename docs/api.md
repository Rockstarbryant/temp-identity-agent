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
| GET | `/api/registration-jobs/{id}/` | — | Includes full `steps` audit trail. |
| POST | `/api/registration-jobs/{id}/resume/` | — | Only valid from `captcha_required`/`human_action_required`. `400` otherwise. |
| POST | `/api/registration-jobs/{id}/cancel/` | — | Only valid for non-terminal jobs. `400` otherwise. |

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
