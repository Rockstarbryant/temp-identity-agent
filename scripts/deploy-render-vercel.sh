#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy Temporary Identity Agent
#   Backend  → Render  (Docker web + celery worker + celery beat)
#   Frontend → Vercel  (Next.js)
#
# Prerequisites (install once):
#   - git, curl, jq
#   - Render CLI   :  https://render.com/docs/cli   (optional but convenient)
#   - Vercel CLI   :  npm i -g vercel
#   - Accounts     :  Render, Vercel, Neon (Postgres), Upstash (Redis),
#                     Agent Router / OpenRouter key, Groq key
#
# Usage:
#   chmod +x scripts/deploy-render-vercel.sh
#   ./scripts/deploy-render-vercel.sh
# -----------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "============================================================"
echo " Temporary Identity Agent — Render + Vercel deploy helper"
echo "============================================================"
echo

# ---------------------------------------------------------------------------
# 0. Sanity checks
# ---------------------------------------------------------------------------
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required tool: $1"; exit 1; }; }
need git
need curl

if [[ ! -f backend/manage.py ]]; then
  echo "ERROR: Run this from the project root (backend/manage.py not found)."
  exit 1
fi

# ---------------------------------------------------------------------------
# 1. Secrets checklist
# ---------------------------------------------------------------------------
echo ">> Step 1 — Collect secrets (you will paste these into Render + Vercel)"
echo
cat <<'EOF'
Required values:

  [ ] DJANGO_SECRET_KEY          (python -c "import secrets; print(secrets.token_urlsafe(50))")
  [ ] CREDENTIAL_ENCRYPTION_KEY  (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  [ ] DATABASE_URL               (Neon connection string, sslmode=require)
  [ ] REDIS_URL                  (Upstash rediss://... URL)
  [ ] AGENT_ROUTER_API_KEY
  [ ] AGENT_ROUTER_BASE_URL      (e.g. https://agentrouter.org/v1 or OpenRouter base)
  [ ] AGENT_ROUTER_MODEL
  [ ] GROQ_API_KEY               (https://console.groq.com)
  [ ] GROQ_MODEL                 (default: llama-3.3-70b-versatile)

EOF

read -r -p "Press Enter when you have all secrets ready… "

# ---------------------------------------------------------------------------
# 2. Ensure production files are present
# ---------------------------------------------------------------------------
echo
echo ">> Step 2 — Checking production files"

for f in \
  render.yaml \
  backend/ai/providers/groq.py \
  backend/ai/providers/fallback.py \
  backend/apps/common/views.py \
  docker/Dockerfile.backend
do
  if [[ ! -f "$f" ]]; then
    echo "WARNING: $f is missing. Apply the update package first."
  else
    echo "  OK  $f"
  fi
done

# ---------------------------------------------------------------------------
# 3. Backend on Render
# ---------------------------------------------------------------------------
echo
echo ">> Step 3 — Deploy backend on Render"
echo
cat <<'EOF'
Option A — Blueprint (recommended)

  1. Push this repo to GitHub/GitLab.
  2. https://dashboard.render.com → New → Blueprint
  3. Select the repo. Render reads render.yaml.
  4. Fill in the "sync: false" env vars when prompted:
       DJANGO_ALLOWED_HOSTS      = <service-name>.onrender.com
       DATABASE_URL              = neon connection string
       REDIS_URL                 = upstash rediss://…
       CORS_ALLOWED_ORIGINS      = https://<your-app>.vercel.app   (set after Vercel deploy)
       AGENT_ROUTER_API_KEY / BASE_URL / MODEL
       GROQ_API_KEY
       CREDENTIAL_ENCRYPTION_KEY
  5. Deploy. Note the public URL, e.g. https://tia-backend.onrender.com

Option B — Manual services

  Create three Docker services pointing at docker/Dockerfile.backend:
    - Web    command: migrate + collectstatic + gunicorn … --bind 0.0.0.0:$PORT
    - Worker command: celery -A config worker -l
... 