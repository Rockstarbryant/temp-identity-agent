# Deployment

## Docker Compose (local / small deployments)

```bash
cp .env.example .env
# fill in real values — at minimum DJANGO_SECRET_KEY, CREDENTIAL_ENCRYPTION_KEY,
# AGENT_ROUTER_*, and a real EMAIL_API_BASE_URL if not using mail.tm's default
docker compose -f docker/docker-compose.yml up --build
```

This brings up Postgres, Redis, the Django backend (migrates then runs
gunicorn), a Celery worker, Celery beat, and the frontend in **dev
mode** (`target: dev` in `docker-compose.yml` — hot reload, not an
optimized build).

### Building the frontend for production instead

```bash
docker build -f docker/Dockerfile.frontend --target prod \
  --build-arg NEXT_PUBLIC_API_URL=https://your-real-api.example \
  -t temp-identity-agent-frontend:prod ..
```

`NEXT_PUBLIC_*` variables are baked in at build time, not read at
container start — pass the real API URL as a build arg, not just a
runtime env var, for the `prod` target.

### Backend production requirements

The backend Dockerfile defaults to `requirements/development.txt`.
For production, build with:

```bash
docker build -f docker/Dockerfile.backend \
  --build-arg REQUIREMENTS_FILE=production.txt \
  -t temp-identity-agent-backend:prod ..
```

And point `DJANGO_SETTINGS_MODULE=config.settings.production` (set in
your `.env` or the container's environment).

## Non-root by default

Both the backend and frontend `prod` images run as a dedicated
`appuser`, not root. Playwright's browser binaries are installed to
`/app/.playwright-browsers` (set via `PLAYWRIGHT_BROWSERS_PATH`)
specifically so they're owned by that user after the ownership
transfer, not stranded under `/root`.

## Healthchecks

Both Dockerfiles define a `HEALTHCHECK`; `docker-compose.yml` uses
`condition: service_healthy` so Celery workers/beat wait for the
backend to actually be serving requests (post-migration) before
starting, and the frontend waits for the backend too.

## What's verified vs. not

**Verified**: Dockerfile and compose YAML syntax (via real parsers —
`dockerfile-parse`, `PyYAML`), every `COPY` source path actually
exists in the repo, multi-stage build structure.

**Not verified**: an actual `docker build`/`docker compose up` run —
this sandbox has no Docker daemon (`docker: not found`). Run it
yourself before deploying; if anything doesn't build cleanly, the most
likely culprits are pinned dependency versions drifting (Python/Node
base images are pinned but package versions in `requirements/*.txt`
and `package.json` are exact-pinned specifically to reduce this risk)
or the Playwright `apt-get`-based system dependency install, which
needs real network access to Debian's package mirrors at build time.

## Retention / cleanup

Celery beat runs `expire_temporary_identities`,
`expire_stale_registration_jobs`, and `close_orphaned_browser_sessions`
on the schedule in `config/settings/base.py`'s `CELERY_BEAT_SCHEDULE`.
`TEMP_ACCOUNT_RETENTION_DAYS` (default 7) controls how long identities
live before being scrubbed.
