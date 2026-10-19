# Django admin

The admin site lives at `https://<your-api-host>/admin/` (for example `https://logindirect.onrender.com/admin/`).

## Who can sign in

Only users with `is_staff` set. Normal app accounts cannot. Create the first admin one of two ways:

- **Environment variables (no shell needed, works on Render's free plan).** Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` (and optionally `ADMIN_EMAIL`) on the web service and redeploy. The start command runs `python manage.py ensure_admin`, which creates the superuser or resets its password. Delete `ADMIN_PASSWORD` from the environment afterwards if you do not want it stored there.
- **Shell.** `python manage.py createsuperuser`.

## What you can do there

| Section | Access |
|---|---|
| Domain policies | Add / edit / delete. Block a website, mark it unsupported, or require a human. |
| Target websites, Users | Add / edit. |
| Jobs, steps, questions, identities, vault accounts, API keys, OAuth records, mailboxes, agent sessions, audit log | View only |

API keys also have a "Revoke selected keys" action. The audit log cannot be deleted.

## What is never shown

Encrypted or hashed columns are excluded from every page, even for superusers: stored passwords and answers, profile values, mailbox secrets, connected-account passwords and browser sessions, API key and OAuth hashes, email bodies, OTP codes and verification links.
