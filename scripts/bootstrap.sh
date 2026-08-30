#!/usr/bin/env bash
# One-shot local setup: backend venv + deps, generated secrets, migrations, frontend deps.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Backend"
cd backend
python3 -m venv .venv 2>/dev/null || true
. .venv/bin/activate 2>/dev/null || . .venv/Scripts/activate
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Generating .env with fresh secrets"
  cp .env.example .env
  JWT=$(python -c 'import secrets;print(secrets.token_urlsafe(64))')
  FEK=$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')
  python - "$JWT" "$FEK" <<'PY'
import sys, pathlib
jwt, fek = sys.argv[1], sys.argv[2]
p = pathlib.Path('.env'); t = p.read_text().splitlines()
out = []
for line in t:
    if line.startswith('JWT_SECRET='): line = f'JWT_SECRET={jwt}'
    if line.startswith('FIELD_ENCRYPTION_KEY='): line = f'FIELD_ENCRYPTION_KEY={fek}'
    out.append(line)
p.write_text('\n'.join(out) + '\n')
PY
fi

echo "==> Migrations"
alembic upgrade head

echo "==> Frontend"
cd ../frontend
npm install

echo
echo "Done. Start with:"
echo "  Terminal 1: cd mock-agent && uvicorn main:app --port 9100"
echo "  Terminal 2: cd backend   && uvicorn app.main:app --reload --port 8000"
echo "  Terminal 3: cd frontend  && npm run dev"
