#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/install.sh
npm ci --prefix frontend
npm run build --prefix frontend
if [ -n "${AGENTEVAL_DATABASE_URL:-}" ]; then
  .venv/bin/alembic upgrade head
else
  .venv/bin/python scripts/local_db.py start
  .venv/bin/python scripts/local_db.py admin .venv/bin/alembic upgrade head
fi
