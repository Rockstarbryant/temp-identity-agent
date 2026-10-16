# Troubleshooting

## `playwright install` fails / browser won't launch

```
Error BrowserType.launch: Executable doesn't exist at .../headless_shell
```

Run `playwright install --with-deps chromium` in the same environment
that runs the Celery worker (not just where Django itself runs) — the
Dockerfile does this automatically, but a bare-metal/venv setup needs
it run explicitly. This is the single most likely first failure when
standing the project up — verify it early.

## `CREDENTIAL_ENCRYPTION_KEY` errors

```
CredentialEncryptionError: CREDENTIAL_ENCRYPTION_KEY is not configured.
```

Generate one and put it in `.env`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Changing this key after identities/mailboxes already exist makes their
stored secrets undecryptable — treat it like any other production
secret (rotate deliberately, not casually).

## Jobs stuck in `QUEUED`

Almost always means the Celery worker isn't running, or isn't
connected to the same Redis instance as Django. Check
`celery -A config worker -l info` is running and `REDIS_URL` matches
between the web process and the worker.

## `429 Too Many Requests` during local testing

The `auth` (5/min) and `registration_jobs` (10/hour) throttle scopes
are real and apply in every environment, including local dev. If
you're scripting repeated logins/job creations, either wait, raise the
limits in `DEFAULT_THROTTLE_RATES` for local testing, or (in
automated tests) clear Django's cache between test cases — see
`conftest.py`'s `_reset_throttle_cache` fixture for why this bit us
during Phase 13 and how it's handled.

## mail.tm mailbox creation fails

Check `EMAIL_API_BASE_URL` is reachable from wherever the Celery
worker runs — this sandbox's own network couldn't reach it, which is
why `scripts/live_smoke_test_mailtm.py` exists as a standalone way to
verify it in your actual environment.

## OpenRouter requests fail or keep falling back to Groq

```
WARNING Primary AI provider (openrouter) failed (OpenRouter returned 429: ...); falling back to groq
```

Expected occasionally: `openrouter/free` is rate-limited. If it happens on
every call, check `OPENROUTER_API_KEY`, and whether your account has hit the
daily free-model cap (adding credits raises it). A `401` is *not* retried on
Groq — fix the key. If both providers fail, the error message includes both.
Shared request/response handling is in `ai/providers/openai_compat.py`.

## Frontend can't reach the backend (CORS errors)

Confirm `NEXT_PUBLIC_API_URL` (frontend) and `CORS_ALLOWED_ORIGINS`
(backend) actually point at each other. `development.py` sets
`CORS_ALLOW_ALL_ORIGINS = True` for local convenience;
`production.py` does not — set `CORS_ALLOWED_ORIGINS` explicitly for
any real deployment.

## A job fails immediately with `DOMAIN_BLOCKED` or goes straight to `HUMAN_ACTION_REQUIRED`

Check `DomainPolicy` in the Django admin — an admin may have
explicitly blocked or human-gated that domain. This is working as
designed (see `docs/security.md`), not a bug.
