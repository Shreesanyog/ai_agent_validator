# One-shot local setup for Windows PowerShell.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==> Backend"
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

if (-Not (Test-Path .env)) {
  Write-Host "==> Generating .env with fresh secrets"
  Copy-Item .env.example .env
  $jwt = python -c "import secrets;print(secrets.token_urlsafe(64))"
  $fek = python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
  (Get-Content .env) `
    -replace '^JWT_SECRET=.*', "JWT_SECRET=$jwt" `
    -replace '^FIELD_ENCRYPTION_KEY=.*', "FIELD_ENCRYPTION_KEY=$fek" |
    Set-Content .env
}

Write-Host "==> Migrations"
alembic upgrade head

Write-Host "==> Frontend"
Set-Location ..\frontend
npm install

Write-Host ""
Write-Host "Done. Start with:"
Write-Host "  Terminal 1: cd mock-agent; uvicorn main:app --port 9100"
Write-Host "  Terminal 2: cd backend;    uvicorn app.main:app --reload --port 8000"
Write-Host "  Terminal 3: cd frontend;   npm run dev"
