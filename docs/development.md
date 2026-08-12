# Development

## Prerequisites

- Python 3.12+
- Node.js 22+
- PostgreSQL 16 (or Docker)
- Redis 7 (or Docker)

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements/development.txt
playwright install --with-deps chromium

cp ../.env.example ../.env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste that into CREDENTIAL_ENCRYPTION_KEY in ../.env

# start Postgres + Redis (locally or via `docker compose -f docker/docker-compose.yml up postgres redis -d`)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Running Celery

```bash
# separate terminals, same venv:
celery -A config worker -l info
celery -A config beat -l info
```

## Frontend setup

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

## Running tests

```bash
cd backend
export DJANGO_SECRET_KEY=test-key
export CREDENTIAL_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export DATABASE_URL=sqlite:///test.db
python -m pytest
```

75 tests, organized one `tests/` package per Django app. See
`docs/testing.md` for what's covered and — importantly — what isn't
(and why).

## Frontend lint/build

```bash
cd frontend
npx eslint .
npm run build
```

## Local mock registration sites (for browser-automation testing)

```bash
python backend/tests/fixtures/serve_mock_sites.py 8899
# -> http://127.0.0.1:8899/simple_registration.html, etc.
```

Six fixtures: simple, email-verification, multi-step (2 pages),
failing, CAPTCHA, and a deliberately unusual page structure (also
contains an inert prompt-injection probe — see `docs/security.md`).

## Code quality

```bash
cd backend
ruff check .
black --check .
mypy .   # requires django-stubs, already in requirements/development.txt
```

## Project structure

```
backend/config/          Django settings, urls, celery app
backend/apps/             one Django app per domain area
backend/ai/                AI provider abstraction (provider-agnostic)
backend/tests/fixtures/    local mock registration sites (not live sites)
frontend/                  Next.js App Router
docker/                    Dockerfile.backend, Dockerfile.frontend (multi-stage), docker-compose.yml
docs/                      this directory
scripts/                   standalone scripts (e.g. the mail.tm live smoke test)
```
