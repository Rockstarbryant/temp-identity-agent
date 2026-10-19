# Vault mailbox, notifications, site playbooks, manual sign-up kit

## Vault mailbox
`GET /api/accounts/<id>/mailbox/[?refresh=1]`, `.../mailbox/messages/<mid>/`, `POST .../mailbox/ask/` (agent answers from the inbox, no tools, mail treated as untrusted data; throttle scope `mailbox_ask`). MCP tools: `list_accounts`, `check_mailbox`.

## Notifications
`/api/notifications/` (list, clear), `read/`, `<id>/`, `stream/` (SSE; fetch + Authorization header, resumes via `Last-Event-ID`, ends after `NOTIFICATION_STREAM_SECONDS`, default 55). Events: job started/completed/failed/cancelled/needs you/question, new mail, account expiring/expired, client connected, manual saved. Background mail polling: Celery beat `poll-mailboxes` (60s); open tabs also poll through the stream.
gunicorn now runs `--worker-class gthread --threads 8` so open streams don't starve workers.

## Site playbooks
After a successful registration the form-filling phase is saved per domain (`SitePlaybook`). Values are stored as sources (email, password, profile:key), never literals. Next run replays the steps through the normal tool dispatch, then the AI continues (verification). Any mismatch aborts replay and the AI carries on; 3 failures auto-disable. Manage in Django admin.

## Manual sign-up kit
When a CAPTCHA/human step stops a registration, the form's fields are saved (descriptors only). `POST /api/registration-jobs/<id>/manual-kit/` returns them with values (audit-logged); `POST .../manual-complete/` saves the account to the vault (optionally with the username/password actually used). Mail keeps arriving in the vault mailbox.

## Deploy
Redeploy API (migrations run on start), rebuild the worker image, run a Celery beat process for background polling.
