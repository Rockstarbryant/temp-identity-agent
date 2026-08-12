# Temp Identity Agent — Complete Local & Production Setup Guide

> A complete step-by-step guide for setting up, running, testing, and deploying the Temp Identity Agent project.
>
> This guide covers both a normal Linux/PC environment and an Android phone using Termux + Ubuntu/PRoot.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Project Architecture](#2-project-architecture)
3. [Requirements](#3-requirements)
4. [Cloning the Repository](#4-cloning-the-repository)
5. [Android Setup with Termux](#5-android-setup-with-termux)
6. [Ubuntu/PRoot Environment](#6-ubuntuproot-environment)
7. [Backend Directory](#7-backend-directory)
8. [Python Virtual Environment](#8-python-virtual-environment)
9. [Installing Backend Dependencies](#9-installing-backend-dependencies)
10. [Environment Variables](#10-environment-variables)
11. [PostgreSQL Setup](#11-postgresql-setup)
12. [Creating the PostgreSQL Database](#12-creating-the-postgresql-database)
13. [Django Database Configuration](#13-django-database-configuration)
14. [Running Django Migrations](#14-running-django-migrations)
15. [Creating a Django Admin User](#15-creating-a-django-admin-user)
16. [Redis Setup](#16-redis-setup)
17. [Redis on Normal Linux](#17-redis-on-normal-linux)
18. [Redis on Android/PRoot](#18-redis-on-androidproot)
19. [Celery Configuration](#19-celery-configuration)
20. [Starting Celery](#20-starting-celery)
21. [Celery on Android](#21-celery-on-android)
22. [Playwright Setup](#22-playwright-setup)
23. [Playwright on Android/PRoot](#23-playwright-on-androidproot)
24. [Starting the Django Backend](#24-starting-the-django-backend)
25. [Django Admin](#25-django-admin)
26. [Testing Authentication](#26-testing-authentication)
27. [Testing Login](#27-testing-login)
28. [Testing /api/me/](#28-testing-apime)
29. [Testing /api/me/ With JWT](#29-testing-apime-with-jwt)
30. [Testing Registration](#30-testing-registration)
31. [First Registration Test](#31-first-registration-test)
32. [Understanding the Registration Job](#32-understanding-the-registration-job)
33. [The Redis Failure We Encountered](#33-the-redis-failure-we-encountered)
34. [The Celery Worker Test](#34-the-celery-worker-test)
35. [Playwright Failure We Encountered](#35-playwright-failure-we-encountered)
36. [Async/Django Error](#36-asyncdjango-error)
37. [Frontend Setup](#37-frontend-setup)
38. [Frontend Environment Variables](#38-frontend-environment-variables)
39. [Running Everything Locally](#39-running-everything-locally)
40. [Recommended Startup Order](#40-recommended-startup-order)
41. [Production Architecture](#41-production-architecture)
42. [Production Components](#42-production-components)
43. [Production Environment Variables](#43-production-environment-variables)
44. [Generate a Strong Django Secret](#44-generate-a-strong-django-secret)
45. [Production PostgreSQL](#45-production-postgresql)
46. [Railway Backend Deployment](#46-railway-backend-deployment)
47. [Railway Redis](#47-railway-redis)
48. [Railway Celery Worker](#48-railway-celery-worker)
49. [Render Backend Deployment](#49-render-backend-deployment)
50. [Render PostgreSQL](#50-render-postgresql)
51. [Render Redis](#51-render-redis)
52. [Render Celery Worker](#52-render-celery-worker)
53. [Why Celery Needs a Separate Worker](#53-why-celery-needs-a-separate-worker)
54. [Vercel Frontend Deployment](#54-vercel-frontend-deployment)
55. [Vercel Environment Variables](#55-vercel-environment-variables)
56. [CORS](#56-cors)
57. [Production HTTPS](#57-production-https)
58. [Playwright in Production](#58-playwright-in-production)
59. [Docker for Production](#59-docker-for-production)
60. [Production Database Migrations](#60-production-database-migrations)
61. [Static Files](#61-static-files)
62. [Django Production Settings](#62-django-production-settings)
63. [Common Error: / Returns 404](#63-common-error--returns-404)
64. [Common Error: /favicon.ico 404](#64-common-error-faviconico-404)
65. [Common Error: /api/ 404](#65-common-error-api-404)
66. [Common Error: 401 Unauthorized](#66-common-error-401-unauthorized)
67. [Common Error: 400 Bad Request](#67-common-error-400-bad-request)
68. [Common Error: Redis Connection Refused](#68-common-error-redis-connection-refused)
69. [Common Error: Celery Cannot Connect to Redis](#69-common-error-celery-cannot-connect-to-redis)
70. [Common Error: Playwright Browser Missing](#70-common-error-playwright-browser-missing)
71. [Common Error: SynchronousOnlyOperation](#71-common-error-synchronousonlyoperation)
72. [Android Development Limitations](#72-android-development-limitations)
73. [Git Workflow](#73-git-workflow)
74. [Fresh Device Setup — Quick Version](#74-fresh-device-setup--quick-version)
75. [Complete Local Checklist](#75-complete-local-checklist)
76. [Complete Production Checklist](#76-complete-production-checklist)
77. [Final Architecture](#77-final-architecture)
78. [The Most Important Lesson](#78-the-most-important-lesson)
79. [Final Recommended Development Strategy](#79-final-recommended-development-strategy)

---

## 1. Introduction

The Temp Identity Agent consists of several services working together.

The Django backend handles:

- Authentication
- API endpoints
- Users
- Registration jobs
- Temporary identities
- Job state
- Database operations
- AI-agent orchestration

Celery handles background tasks.

Redis acts as the Celery message broker and result backend.

PostgreSQL stores persistent application data.

Playwright provides browser automation.

The frontend provides the user interface.

The basic architecture is:

```text
                     ┌──────────────────┐
                     │     Frontend     │
                     │   Next.js / Web  │
                     └────────┬─────────┘
                              │
                              │ HTTP / REST
                              ▼
                     ┌──────────────────┐
                     │ Django Backend   │
                     │ Django REST API  │
                     └───────┬──────────┘
                             │
             ┌───────────────┼────────────────┐
             │               │                │
             ▼               ▼                ▼
      ┌────────────┐  ┌────────────┐   ┌────────────┐
      │ PostgreSQL │  │   Redis    │   │ Playwright │
      │  Database  │  │   Broker   │   │  Browser   │
      └────────────┘  └─────┬──────┘   └────────────┘
                             │
                             ▼
                     ┌──────────────────┐
                     │ Celery Worker    │
                     │ Background Jobs  │
                     └──────────────────┘
```

---

## 2. Project Architecture

The backend is structured approximately like this:

```text
backend/
├── apps/
│   ├── ai_agent/
│   ├── browser/
│   ├── identities/
│   └── registration/
│
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   │
│   ├── celery.py
│   ├── urls.py
│   └── ...
│
├── manage.py
├── requirements.txt
└── .env
```

The important services are:

- Django
- PostgreSQL
- Redis
- Celery
- Playwright
- Frontend

---

## 3. Requirements

### Normal Linux/macOS/Windows + WSL

You need:

- Git
- Python 3.12+
- PostgreSQL
- Redis
- Node.js
- npm
- Playwright dependencies
- A modern browser environment

For Windows, WSL2 is recommended for the backend if the project is primarily Linux-oriented.

---

## 4. Cloning the Repository

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
```

Enter the project:

```bash
cd temp-identity-agent
```

Check the files:

```bash
ls
```

You should see something similar to:

```text
backend
frontend
README.md
...
```

---

## 5. Android Setup with Termux

The project can be developed on Android.

This is particularly useful when a PC is unavailable.

Install:

- Termux
- Acode or another code editor
- Ubuntu/PRoot environment

Termux provides the Linux-like shell while Ubuntu provides a more complete GNU/Linux userspace.

---

## 6. Ubuntu/PRoot Environment

Inside Termux, enter the Ubuntu environment.

For example:

```bash
proot-distro login ubuntu
```

Verify the system:

```bash
uname -a
```

Check Python:

```bash
python3 --version
```

Check architecture:

```bash
uname -m
```

On an ARM64 Android device you will normally see:

```text
aarch64
```

Update packages:

```bash
apt update
apt upgrade -y
```

Install basic tools:

```bash
apt install -y \
    git \
    curl \
    wget \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev
```

---

## 7. Backend Directory

Move into the backend:

```bash
cd temp-identity-agent/backend
```

Confirm:

```bash
pwd
```

You should be inside:

```text
.../temp-identity-agent/backend
```

---

## 8. Python Virtual Environment

Create the virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Your shell should now show:

```text
(.venv)
```

Verify:

```bash
python --version
```

Example:

```text
Python 3.12.3
```

---

## 9. Installing Backend Dependencies

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

Verify Django:

```bash
python -m django --version
```

Verify Celery:

```bash
celery --version
```

Example:

```text
5.4.0
```

---

## 10. Environment Variables

The project uses environment variables for configuration.

Create the environment file if it doesn't exist:

```bash
touch .env
```

Example development configuration:

```env
DEBUG=True

SECRET_KEY=change-this-development-secret

DATABASE_URL=postgresql://identity_user:password@localhost:5432/identity_agent

REDIS_URL=redis://localhost:6379/0

ALLOWED_HOSTS=127.0.0.1,localhost

CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Do not commit `.env` to Git.

Add it to `.gitignore`:

```text
.env
.venv/
__pycache__/
*.pyc
```

---

## 11. PostgreSQL Setup

PostgreSQL is the primary persistent database.

### Install PostgreSQL

Inside Ubuntu:

```bash
apt update
apt install postgresql postgresql-contrib -y
```

Because PRoot environments generally do not run systemd normally, PostgreSQL may not automatically start.

Check:

```bash
ps aux | grep postgres
```

If PostgreSQL is not running, start it using the environment's PostgreSQL tools.

On a normal Linux system:

```bash
sudo systemctl start postgresql
```

Check:

```bash
sudo systemctl status postgresql
```

On PRoot/Termux, systemd may not be available. In that case PostgreSQL must be started manually using the appropriate cluster command.

---

## 12. Creating the PostgreSQL Database

Enter PostgreSQL:

```bash
sudo -u postgres psql
```

Create the user:

```sql
CREATE USER identity_user WITH PASSWORD 'change-this-password';
```

Create the database:

```sql
CREATE DATABASE identity_agent OWNER identity_user;
```

Grant privileges:

```sql
GRANT ALL PRIVILEGES ON DATABASE identity_agent TO identity_user;
```

Exit:

```sql
\q
```

Test the connection:

```bash
psql \
  -h localhost \
  -U identity_user \
  -d identity_agent
```

If successful:

```text
identity_agent=>
```

Exit:

```sql
\q
```

---

## 13. Django Database Configuration

The project reads the database connection from the environment.

For example:

```env
DATABASE_URL=postgresql://identity_user:password@localhost:5432/identity_agent
```

Make sure the username, password, database name, host and port match your PostgreSQL configuration.

---

## 14. Running Django Migrations

From the backend:

```bash
python manage.py makemigrations
```

Then:

```bash
python manage.py migrate
```

Check:

```bash
python manage.py showmigrations
```

Django should show the migrations as applied.

---

## 15. Creating a Django Admin User

Create a superuser:

```bash
python manage.py createsuperuser
```

Follow the prompts.

Example:

```text
Username:
Email:
Password:
Password (again):
```

This account can be used at:

```text
http://127.0.0.1:8000/admin/
```

---

## 16. Redis Setup

Redis is required by Celery.

Install it:

```bash
apt update
apt install redis-server -y
```

Check:

```bash
redis-server --version
```

Example:

```text
Redis server v=7.0.15
```

---

## 17. Redis on Normal Linux

On a normal Linux machine:

```bash
sudo systemctl start redis
```

Then:

```bash
redis-cli ping
```

Expected:

```text
PONG
```

---

## 18. Redis on Android/PRoot

This was one of the important issues encountered during development.

PRoot does not behave like a normal Linux installation.

Running:

```bash
redis-server --daemonize yes
```

may appear successful but Redis can immediately exit.

The log revealed:

```text
WARNING Your kernel has a bug that could lead to data corruption
Redis will now exit to prevent data corruption.
```

This is related to the ARM64/PRoot kernel environment.

For development testing, Redis can be started while explicitly ignoring the warning.

Create a temporary Redis directory:

```bash
mkdir -p /tmp/redis
```

Start Redis:

```bash
redis-server \
  --bind 127.0.0.1 \
  --port 6379 \
  --dir /tmp/redis \
  --ignore-warnings ARM64-COW-BUG
```

If you want it detached:

```bash
redis-server \
  --bind 127.0.0.1 \
  --port 6379 \
  --dir /tmp/redis \
  --logfile /tmp/redis/redis.log \
  --ignore-warnings ARM64-COW-BUG \
  --daemonize yes
```

Verify:

```bash
redis-cli ping
```

Expected:

```text
PONG
```

Check the process:

```bash
ps aux | grep '[r]edis'
```

Check logs:

```bash
cat /tmp/redis/redis.log
```

You want to see:

```text
Ready to accept connections
```

> **Important:** Ignoring a kernel warning is appropriate only as a development workaround when you understand the risk. It should not be blindly used for production data.

---

## 19. Celery Configuration

The project already contains:

```text
config/celery.py
```

The settings contain:

```python
CELERY_BROKER_URL = env(
    "REDIS_URL",
    default="redis://localhost:6379/0"
)

CELERY_RESULT_BACKEND = env(
    "REDIS_URL",
    default="redis://localhost:6379/0"
)
```

Therefore Redis must be available at:

```text
redis://localhost:6379/0
```

unless `REDIS_URL` overrides it.

---

## 20. Starting Celery

Make sure the virtual environment is active:

```bash
source .venv/bin/activate
```

From the backend directory:

```bash
celery -A config worker --loglevel=info
```

A successful startup looks like:

```text
celery@localhost ready.
```

You should also see:

```text
Connected to redis://localhost:6379/0
```

The worker should list tasks such as:

```text
apps.registration.tasks.run_registration_job_task
apps.registration.tasks.resume_registration_job_task
apps.identities.tasks.close_orphaned_browser_sessions
apps.identities.tasks.expire_stale_registration_jobs
apps.identities.tasks.expire_temporary_identities
```

This confirms that Celery discovered the application's tasks.

---

## 21. Celery on Android

Android/PRoot runs the Celery worker successfully, but remember:

```text
Terminal 1 → Redis
Terminal 2 → Celery
Terminal 3 → Django
Terminal 4 → Frontend
```

Keep each process alive.

If Android kills the terminal process, the service will stop.

Using multiple Termux sessions or a terminal multiplexer can make this easier.

---

## 22. Playwright Setup

The application uses Playwright for browser automation.

Install the browser:

```bash
playwright install chromium
```

Check installed browsers:

```bash
playwright install --list
```

Test Chromium:

```python
from playwright.sync_api import sync_playwright

p = sync_playwright().start()
b = p.chromium.launch(headless=True)
print('CHROMIUM OK')
b.close()
p.stop()
```

Expected:

```text
CHROMIUM OK
```

---

## 23. Playwright on Android/PRoot

Playwright is one of the more difficult components to run inside an Android PRoot environment.

You may see:

```text
BrowserType.launch:
Executable doesn't exist
```

This means the Python package exists but the browser executable has not been installed.

Run:

```bash
playwright install chromium
```

If Chromium refuses to start because Linux libraries are missing, install the dependencies requested by Playwright where possible.

If the required browser libraries are incompatible with the PRoot environment, browser automation may need to be moved to a normal Linux server for production.

This is one reason the Android environment is excellent for development but not necessarily ideal for production browser automation.

---

## 24. Starting the Django Backend

Start Django:

```bash
python manage.py runserver 0.0.0.0:8000
```

Expected:

```text
Starting development server at http://0.0.0.0:8000/
```

The API is now available locally.

From the phone itself:

```text
http://127.0.0.1:8000/
```

The root endpoint may return:

```text
404 Not Found
```

That does not necessarily mean Django is broken.

The project may simply not define a route for `/`.

---

## 25. Django Admin

Open:

```text
http://127.0.0.1:8000/admin/
```

Log in with the superuser created earlier.

If the admin page loads, Django, PostgreSQL and the authentication/session system are functioning.

---

## 26. Testing Authentication

Test login with an empty request:

```bash
curl -i \
  -X POST \
  http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected:

```json
{
  "username": [
    "This field is required."
  ],
  "password": [
    "This field is required."
  ]
}
```

This is actually a good sign.

It means the endpoint exists and validation is working.

---

## 27. Testing Login

Use a valid account:

```bash
curl -s \
  -X POST \
  http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  }'
```

A successful response contains:

```json
{
  "refresh": "...",
  "access": "..."
}
```

The access token is then used for protected endpoints.

---

## 28. Testing /api/me/

Without authentication:

```bash
curl -i \
  http://127.0.0.1:8000/api/me/
```

Expected:

```text
401 Unauthorized
```

with:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

This confirms that authentication protection is working.

---

## 29. Testing /api/me/ With JWT

Store the access token:

```bash
ACCESS_TOKEN="YOUR_ACCESS_TOKEN"
```

Then:

```bash
curl -i \
  http://127.0.0.1:8000/api/me/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Expected:

```text
200 OK
```

---

## 30. Testing Registration

Registration requires:

- Django
- PostgreSQL
- Redis
- Celery
- Playwright

The request flow is:

```text
Frontend
    ↓
POST /api/registration-jobs/
    ↓
Django
    ↓
Create RegistrationJob
    ↓
Celery.delay()
    ↓
Redis
    ↓
Celery Worker
    ↓
Registration Task
    ↓
AI Agent
    ↓
Playwright
```

---

## 31. First Registration Test

Before creating a job, verify Redis:

```bash
redis-cli ping
```

Expected:

```text
PONG
```

Verify Celery is running:

```text
celery@localhost ready.
```

Verify Django is running:

```text
Starting development server at http://0.0.0.0:8000/
```

Then submit a registration job from the frontend.

---

## 32. Understanding the Registration Job

A job may go through states such as:

```text
QUEUED
RUNNING
WAITING
COMPLETED
FAILED
CANCELLED
```

Celery processes the asynchronous portion.

Django remains responsible for persistent job state.

---

## 33. The Redis Failure We Encountered

Initially the application produced:

```text
Connection refused
```

Specifically:

```text
Error 111 connecting to localhost:6379
```

The Django API returned:

```text
500 Internal Server Error
```

The important part of the traceback was:

```text
kombu.exceptions.OperationalError:
Error 111 connecting to localhost:6379
```

The problem was not Django.

It was:

> Redis was not running.

Installing Redis alone was not sufficient because PRoot prevented the service manager from automatically starting it.

After starting Redis correctly, Celery successfully connected.

---

## 34. The Celery Worker Test

Once Redis was running:

```bash
celery -A config worker --loglevel=info
```

The worker reported:

```text
Connected to redis://localhost:6379/0
```

Then:

```text
celery@localhost ready.
```

It successfully received registration tasks.

This proved:

```text
Django → Redis → Celery
```

was functioning.

---

## 35. Playwright Failure We Encountered

After Celery successfully received a registration task, the next failure was:

```text
BrowserType.launch:
Executable doesn't exist
```

The important lesson is:

> Installing the Python Playwright package does not automatically mean the browser executable is installed.

Install Chromium:

```bash
playwright install chromium
```

Then test it independently.

---

## 36. Async/Django Error

During the Playwright failure path another error appeared:

```text
django.core.exceptions.SynchronousOnlyOperation:
You cannot call this from an async context
```

This occurred while the error-handling code attempted a Django database operation from an asynchronous context.

This is an application-code issue rather than a Redis/Celery installation problem.

It should eventually be fixed by restructuring the async/synchronous boundary, for example by using appropriate Django async APIs or `sync_to_async` where necessary.

Do not use:

```python
# arbitrary database calls inside async code
model.save()
```

without considering Django's async restrictions.

---

## 37. Frontend Setup

Open another terminal.

Go to the frontend:

```bash
cd temp-identity-agent/frontend
```

Install dependencies:

```bash
npm install
```

Run development mode:

```bash
npm run dev
```

The frontend will normally start on:

```text
http://localhost:3000
```

---

## 38. Frontend Environment Variables

The frontend needs to know where the backend API lives.

Example:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Depending on the project's implementation, the exact variable name may differ.

Check the frontend code for:

```text
NEXT_PUBLIC_
API_URL
BASE_URL
```

Do not blindly create a different variable name if the application already expects another one.

---

## 39. Running Everything Locally

The complete local environment should look like:

**Terminal 1 — Redis**

```bash
redis-server \
  --bind 127.0.0.1 \
  --port 6379 \
  --dir /tmp/redis \
  --ignore-warnings ARM64-COW-BUG
```

**Terminal 2 — Celery**

```bash
cd backend
source .venv/bin/activate

celery -A config worker --loglevel=info
```

**Terminal 3 — Django**

```bash
cd backend
source .venv/bin/activate

python manage.py runserver 0.0.0.0:8000
```

**Terminal 4 — Frontend**

```bash
cd frontend

npm run dev
```

---

## 40. Recommended Startup Order

Always start services in this order:

```text
1. PostgreSQL
       ↓
2. Redis
       ↓
3. Celery
       ↓
4. Django
       ↓
5. Frontend
```

This makes troubleshooting much easier.

---

## 41. Production Architecture

Local development:

```text
Android/PC
 ├── PostgreSQL
 ├── Redis
 ├── Celery
 ├── Django
 └── Next.js
```

Production:

```text
Internet
                       │
                       ▼
                ┌─────────────┐
                │   Vercel    │
                │  Frontend   │
                └──────┬──────┘
                       │
                       │ HTTPS
                       ▼
                ┌─────────────┐
                │ Railway /   │
                │   Render    │
                │   Django    │
                └──────┬──────┘
                       │
            ┌──────────┼───────────┐
            │          │           │
            ▼          ▼           ▼
       PostgreSQL    Redis      Celery
                              Worker
                                 │
                                 ▼
                             Playwright
```

---

## 42. Production Components

A production deployment requires:

- **Frontend:** Vercel
- **Backend:** Railway or Render
- **Database:** Managed PostgreSQL
- **Redis:** Managed Redis
- **Worker:** Separate Celery worker service
- **Browser automation:** Playwright-compatible Linux environment

---

## 43. Production Environment Variables

Never hard-code secrets.

Backend production variables should include values similar to:

```env
DEBUG=False

SECRET_KEY=<LONG_RANDOM_SECRET>

DATABASE_URL=<PRODUCTION_POSTGRES_URL>

REDIS_URL=<PRODUCTION_REDIS_URL>

ALLOWED_HOSTS=<YOUR_BACKEND_DOMAIN>

CORS_ALLOWED_ORIGINS=https://<YOUR-FRONTEND-DOMAIN>
```

If the project uses additional secrets, add them as well.

Examples could include:

```env
AI_API_KEY=
EMAIL_API_KEY=
ENCRYPTION_KEY=
```

Use the actual names defined by the project.

---

## 44. Generate a Strong Django Secret

Never reuse:

```env
SECRET_KEY=change-me
```

Generate a strong secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the result into the production environment.

---

## 45. Production PostgreSQL

Do not use SQLite for the production application if PostgreSQL is part of the intended architecture.

Use managed PostgreSQL from:

- Railway
- Render
- Supabase
- Neon
- another reputable PostgreSQL provider

The provider will give you a connection string similar to:

```text
postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

Put it into:

```env
DATABASE_URL=
```

---

## 46. Railway Backend Deployment

Create a Railway project.

Connect the GitHub repository.

Select the backend as the service directory if necessary.

Configure:

```text
Root Directory:
backend
```

Add environment variables.

Build/install command:

```bash
pip install -r requirements.txt
```

Run migrations during deployment or as a release command:

```bash
python manage.py migrate
```

Start Django using a production WSGI/ASGI server.

For example:

```bash
gunicorn config.wsgi:application
```

If the project uses ASGI:

```bash
gunicorn config.asgi:application
```

Use the project's actual configuration.

---

## 47. Railway Redis

Create a Redis service or use a managed Redis provider.

Obtain:

```text
REDIS_URL
```

It may look like:

```text
redis://...
```

Set:

```env
REDIS_URL=<YOUR_REDIS_URL>
```

The backend and Celery worker must use the same Redis service.

---

## 48. Railway Celery Worker

The Django web service and Celery worker should be separate processes/services.

Create another Railway service using the same repository.

Use:

```bash
celery -A config worker --loglevel=info
```

Both services must share:

```text
DATABASE_URL
REDIS_URL
SECRET_KEY
```

and any other required environment variables.

Architecture:

```text
Railway
│
├── Django Web Service
│
├── Celery Worker
│
├── PostgreSQL
│
└── Redis
```

---

## 49. Render Backend Deployment

Render can also host the Django backend.

Create a new Web Service.

Connect the GitHub repository.

Set:

```text
Root Directory:
backend
```

Build command:

```bash
pip install -r requirements.txt
```

Run migrations:

```bash
python manage.py migrate
```

Start command:

```bash
gunicorn config.wsgi:application
```

Again, use the actual WSGI module from the project.

---

## 50. Render PostgreSQL

Create a PostgreSQL database in Render.

Render will provide connection details.

Set:

```env
DATABASE_URL=<RENDER_POSTGRES_URL>
```

Run:

```bash
python manage.py migrate
```

---

## 51. Render Redis

Use a compatible Redis provider and set:

```env
REDIS_URL=<REDIS_CONNECTION_URL>
```

The Django web service and Celery worker must use the same Redis URL.

---

## 52. Render Celery Worker

Create a separate Render Background Worker.

Build:

```bash
pip install -r requirements.txt
```

Start:

```bash
celery -A config worker --loglevel=info
```

The worker must have the same:

```text
DATABASE_URL
REDIS_URL
SECRET_KEY
```

as the Django service.

---

## 53. Why Celery Needs a Separate Worker

Django should not perform long-running registration tasks directly inside the HTTP request.

Instead:

```text
Browser
   ↓
Django API
   ↓
Create Job
   ↓
Celery.delay()
   ↓
HTTP response
```

The worker then processes:

```text
Registration Job
       ↓
AI Agent
       ↓
Browser Automation
       ↓
Database Updates
```

This prevents long-running jobs from blocking web requests.

---

## 54. Vercel Frontend Deployment

Push the frontend to GitHub.

Open Vercel.

Create a new project.

Import the repository.

Configure the frontend directory if it is inside:

```text
/frontend
```

Vercel will detect Next.js automatically in most cases.

Build command:

```bash
npm run build
```

Start command is normally handled automatically by Vercel.

---

## 55. Vercel Environment Variables

Set:

```env
NEXT_PUBLIC_API_URL=https://your-backend-domain.example.com
```

Use the actual variable expected by the project.

Do not use:

```text
http://localhost:8000
```

in production.

The frontend must communicate with the public backend URL.

---

## 56. CORS

The backend must allow requests from the Vercel frontend.

Development:

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Production:

```env
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

If you have a custom domain:

```env
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

Do not solve CORS by blindly allowing:

```text
*
```

in a production application that uses authentication.

---

## 57. Production HTTPS

The production architecture should use:

```text
Frontend
   HTTPS
     ↓
Backend
   HTTPS
     ↓
PostgreSQL / Redis
```

Never expose sensitive authentication credentials over plain HTTP.

---

## 58. Playwright in Production

This is one of the most important deployment considerations.

The backend does not simply need Python.

It needs:

```text
Python
Django
Celery
Playwright
Chromium
Linux browser dependencies
```

Therefore your production environment must support browser automation.

A basic Python web service may not automatically contain everything required by Playwright.

You may need:

- A custom Docker image
- A Playwright-compatible base image
- Browser dependencies
- Sufficient memory
- A worker service capable of running Chromium

This should be tested before production launch.

---

## 59. Docker for Production

For browser automation, Docker can make the environment reproducible.

A production container can contain:

```text
Python
Django
Celery
Playwright
Chromium
System dependencies
```

This is often more reliable than manually installing browser dependencies on a server.

---

## 60. Production Database Migrations

Every time database schema changes:

```bash
python manage.py makemigrations
```

Commit the migration files:

```bash
git add .
git commit -m "Add database migration"
git push
```

Production:

```bash
python manage.py migrate
```

Never delete production migration files casually.

---

## 61. Static Files

Django admin and other static assets may require:

```bash
python manage.py collectstatic --noinput
```

Your production deployment should configure Django static files appropriately.

---

## 62. Django Production Settings

Ensure:

```env
DEBUG=False
```

Configure:

- `ALLOWED_HOSTS`
- CORS
- CSRF trusted origins
- SECURE cookies
- HTTPS
- static files

Do not deploy with development settings accidentally enabled.

---

## 63. Common Error: / Returns 404

You may see:

```text
GET / HTTP/1.1 404
```

This is not necessarily an error in the server.

It simply means there is no route registered for `/`.

Test actual endpoints instead:

```text
/api/auth/login/
/api/auth/register/
/api/me/
/api/registration-jobs/
```

---

## 64. Common Error: /favicon.ico 404

You may also see:

```text
GET /favicon.ico 404
```

This simply means Django doesn't have a favicon at that URL.

It does not indicate that the API is broken.

---

## 65. Common Error: /api/ 404

If:

```text
GET /api/ 404
```

but:

```text
POST /api/auth/login/
```

works, then `/api/` itself may simply not be registered.

This is normal for APIs that don't have an API index endpoint.

---

## 66. Common Error: 401 Unauthorized

Example:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

This means the endpoint requires authentication.

Send:

```text
Authorization: Bearer YOUR_ACCESS_TOKEN
```

---

## 67. Common Error: 400 Bad Request

Example:

```json
{
  "username": [
    "This field is required."
  ],
  "password": [
    "This field is required."
  ]
}
```

This means validation failed.

The endpoint is actually responding correctly.

Send the required fields.

---

## 68. Common Error: Redis Connection Refused

Error:

```text
Error 111 connecting to localhost:6379
```

Check:

```bash
redis-cli ping
```

If you get:

```text
Connection refused
```

Redis is not running or is not listening on the expected port.

Check:

```bash
ps aux | grep '[r]edis'
```

Check:

```bash
ss -lntp | grep 6379
```

Then inspect logs.

---

## 69. Common Error: Celery Cannot Connect to Redis

Check:

```bash
grep -R "CELERY_BROKER_URL\|CELERY_RESULT_BACKEND" \
    -n config/settings
```

Verify:

```env
REDIS_URL=redis://localhost:6379/0
```

Then test:

```bash
redis-cli ping
```

Finally restart Celery:

```bash
celery -A config worker --loglevel=info
```

---

## 70. Common Error: Playwright Browser Missing

Error:

```text
Executable doesn't exist
```

Run:

```bash
playwright install chromium
```

Then:

```bash
playwright install --list
```

Test:

```python
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch(headless=True)
print('CHROMIUM OK')
b.close()
p.stop()
```

---

## 71. Common Error: SynchronousOnlyOperation

Error:

```text
You cannot call this from an async context
```

This usually means synchronous Django ORM work is being performed from asynchronous code.

Investigate the relevant code path.

Typical solutions involve:

```python
sync_to_async(...)
```

or Django's async ORM APIs where appropriate.

Do not randomly add async everywhere.

The application's async boundaries should be designed deliberately.

---

## 72. Android Development Limitations

Developing on Android is impressive and useful, but it has limitations.

### Advantages

- No PC required
- Portable
- Git works
- Python works
- Django works
- PostgreSQL can work
- Redis can work
- Celery can work
- Node/npm can work
- Acode provides convenient editing

### Disadvantages

- Android can kill background processes
- PRoot isn't a normal Linux kernel
- systemd isn't normally available
- Browser automation is harder
- Chromium dependencies can be difficult
- ARM64 compatibility can cause issues
- Battery consumption
- Limited RAM
- Thermal throttling
- Multiple services require multiple terminal sessions
- Long-running workers may stop if Android kills Termux

For these reasons:

> Android is excellent for development, debugging and emergency coding, but production workloads should normally run on a proper Linux server.

---

## 73. Git Workflow

After making changes:

```bash
git status
```

Review:

```bash
git diff
```

Stage:

```bash
git add .
```

Commit:

```bash
git commit -m "Update registration agent"
```

Push:

```bash
git push
```

Never commit:

- `.env`
- passwords
- API keys
- JWT secrets
- database credentials
- private keys

---

## 74. Fresh Device Setup — Quick Version

For a completely new machine:

```bash
git clone <REPOSITORY>
cd temp-identity-agent/backend
```

Create environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install:

```bash
pip install -r requirements.txt
```

Install PostgreSQL.

Create:

- database
- user
- password

Configure:

```env
DATABASE_URL=
```

Install Redis:

```bash
apt install redis-server -y
```

Start Redis.

Verify:

```bash
redis-cli ping
```

Expected:

```text
PONG
```

Run migrations:

```bash
python manage.py migrate
```

Create admin:

```bash
python manage.py createsuperuser
```

Install Playwright browser:

```bash
playwright install chromium
```

Start Celery:

```bash
celery -A config worker --loglevel=info
```

Start Django:

```bash
python manage.py runserver 0.0.0.0:8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

---

## 75. Complete Local Checklist

Before reporting a bug, verify each item.

**Python**

```bash
python --version
```

**Virtual environment**

```bash
which python
```

Should point inside:

```text
.venv/
```

**Django**

```bash
python manage.py check
```

Expected:

```text
System check identified no issues
```

**PostgreSQL**

Test connection.

**Redis**

```bash
redis-cli ping
```

Expected:

```text
PONG
```

**Celery**

```bash
celery -A config worker --loglevel=info
```

Expected:

```text
Connected to redis://...
celery@... ready.
```

**Playwright**

```bash
playwright install --list
```

**Chromium**

Run the browser test.

**Django**

```bash
python manage.py runserver
```

**Frontend**

```bash
npm run dev
```

---

## 76. Complete Production Checklist

Before production:

- [ ] `DEBUG=False`
- [ ] Strong `SECRET_KEY`
- [ ] Production PostgreSQL
- [ ] Production Redis
- [ ] Django web service
- [ ] Celery worker
- [ ] Playwright browser available
- [ ] Database migrations applied
- [ ] Static files configured
- [ ] CORS configured
- [ ] CSRF configured
- [ ] HTTPS enabled
- [ ] Frontend deployed
- [ ] Backend deployed
- [ ] Frontend API URL configured
- [ ] Environment variables configured
- [ ] Secrets not committed to Git
- [ ] Authentication tested
- [ ] Registration job tested
- [ ] Celery job processing tested
- [ ] Error handling tested
- [ ] Logs monitored

---

## 77. Final Architecture

The final system looks like this:

```text
USER
                          │
                          ▼
                  ┌───────────────┐
                  │    Vercel     │
                  │ Next.js       │
                  │ Frontend      │
                  └───────┬───────┘
                          │
                       HTTPS
                          │
                          ▼
                  ┌───────────────┐
                  │ Railway /     │
                  │ Render        │
                  │ Django API    │
                  └───────┬───────┘
                          │
              ┌───────────┼────────────┐
              │           │            │
              ▼           ▼            ▼
       ┌────────────┐ ┌─────────┐ ┌─────────────┐
       │ PostgreSQL │ │  Redis  │ │ Other APIs  │
       │            │ │         │ │ / Services  │
       └────────────┘ └────┬────┘ └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Celery       │
                    │ Worker       │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ AI Agent     │
                    │ Orchestrator │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Playwright   │
                    │ Chromium     │
                    └──────────────┘
```

---

## 78. The Most Important Lesson

The project is not simply:

```text
Django + React
```

It is a distributed application composed of multiple services:

```text
Frontend
   +
Django
   +
PostgreSQL
   +
Redis
   +
Celery
   +
Playwright
   +
AI Agent
```

If one critical service is unavailable, another component may fail.

For example:

```text
Redis OFF
   ↓
Celery cannot receive jobs
   ↓
Registration endpoint may fail
```

Or:

```text
Celery ON
   ↓
Playwright browser missing
   ↓
Registration task fails
```

Or:

```text
Playwright fails
   ↓
Error handler executes
   ↓
Async/sync ORM boundary bug
   ↓
Additional exception
```

Understanding these dependencies makes debugging much easier.

---

## 79. Final Recommended Development Strategy

When something breaks, don't immediately change the code.

Test each layer independently.

**Layer 1**

```bash
redis-cli ping
```

**Layer 2**

```bash
celery -A config worker --loglevel=info
```

**Layer 3**

```bash
python manage.py check
```

**Layer 4**

```bash
python manage.py runserver
```

**Layer 5**

Test authentication.

**Layer 6**

Test registration job creation.

**Layer 7**

Verify Celery receives the job.

**Layer 8**

Verify Playwright launches Chromium.

**Layer 9**

Verify the agent executes.

**Layer 10**

Verify the final database state.

This layered approach prevents wasting hours debugging the wrong component.

---

## Conclusion

Getting a modern full-stack AI application running locally can involve considerably more than installing Python and running Django.

The complete stack needs to be understood as a collection of cooperating services:

```text
PostgreSQL
    ↓
Django
    ↓
Redis
    ↓
Celery
    ↓
AI Agent
    ↓
Playwright
    ↓
Browser
```

The frontend then communicates with the Django API:

```text
Next.js
   ↓
Django REST API
```

On a development computer these services can run locally.

On Android, Termux and a Linux/PRoot environment can provide a surprisingly capable development environment, although browser automation and long-running services require additional care.

For production, the recommended architecture is:

```text
Vercel
   ↓
Railway / Render
   ↓
Managed PostgreSQL
   +
Managed Redis
   +
Celery Worker
   +
Playwright-compatible environment
```

Once every component is understood independently, setting up the project on another device becomes a repeatable process rather than a trial-and-error exercise.

The goal of this guide is therefore not just to get the project running once, but to make the setup reproducible for the next computer, phone, developer, or deployment.

### One important note

I deliberately **did not invent exact commands for things that depend on the repository's actual implementation**, such as the precise frontend framework scripts, production settings module, database configuration implementation, or Docker/Playwright image. Those should be taken directly from the repo rather than guessed.

If you want this to become the **definitive `README.md` for your actual repository**, the next step should be an audit of the uploaded project files so I can replace those placeholders with the **exact commands, environment variables, service names, API endpoints, deployment configuration, and directory structure from your codebase**.
