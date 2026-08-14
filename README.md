# AVaaS Enterprise V3 — No Docker

Production-style, multi-tenant Agent Validator as a Service aligned with the included TechCon 2026 proposal. 
## What is implemented

- React + TypeScript + Tailwind CSS 3 dashboard.
- FastAPI backend with tenant/user/membership/project/target/run/result mappings.
- JWT access tokens, rotating hashed refresh tokens, Argon2 passwords, RBAC, encrypted target credentials, and audit events.
- Browser-hosted agent testing using local Playwright Chromium; no Playwright API key is required.
- OpenAPI discovery and extension modes for mapped REST and transcript validation.
- Optional business requirements: the LLM may infer generic scenarios from discovery evidence, but inferred statements are never authoritative business rules.
- Ollama first with one bounded Gemini 2.5 Flash fallback call.
- Rule, safety/hallucination, and optional business/MVP evaluation with composite scores.
- Langfuse primary tracing, OpenTelemetry primary alternative, LangSmith commercial fallback, and persisted local evidence if exporters fail.
- DeepEval dependency and configuration for evaluation-extension integration.
- Baseline/candidate data model and release-gate outputs.
- SQLite local default; PostgreSQL recommended for production.


## Prerequisites

- Windows 11 recommended for local development.
- Python 3.12 64-bit.
- Node.js 22 LTS and npm.
- Ollama, or a Gemini API key.
- Internet access for initial pip/npm/Chromium/model downloads.
- PostgreSQL is not needed locally.

Verify:

```powershell
py --version
node --version
npm --version
```

## Backend installation

```powershell
cd avass-shreesanyog\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip check
python -m playwright install chromium
Copy-Item .env.example .env
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Generate secrets:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Place them in `backend/.env` as `JWT_SECRET` and `FIELD_ENCRYPTION_KEY`.

## SQLite or PostgreSQL

For local development, keep:

```env
APP_ENV=development
DATABASE_URL=sqlite+aiosqlite:///./avaas.db
```

No database server is required. The development backend creates `backend/avaas.db` and its tables. Stop the backend and delete that file only when you intentionally want to reset all local data.

For production, provision PostgreSQL and set:

```env
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE
```

Use Alembic-controlled migrations and PostgreSQL row-level security as defense in depth before production rollout.

## Playwright

No Playwright API key or cloud account is needed. AVaaS runs the installed Chromium binary locally:

```powershell
python -m playwright install chromium
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()"
```

For visible browser debugging:

```env
BROWSER_HEADLESS=false
```

Restart the backend after changing `.env`.

## Ollama primary setup

Install Ollama separately, then:

```powershell
ollama pull llama3.1:8b
ollama serve
```

Verify:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

Set the actual installed model in `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

## Gemini fallback

Set only in `backend/.env` or the hosting secret manager:

```env
GEMINI_API_KEY=YOUR_KEY
GEMINI_MODEL=gemini-2.5-flash
LLM_MAX_ATTEMPTS=1
```

Never place Gemini keys in the React environment, source code, browser storage, screenshots, logs, or Git.

## Langfuse, OpenTelemetry and LangSmith

The proposal requires Langfuse and OpenTelemetry as the open-source-first observability layer and LangSmith as fallback. Configure one or more in `backend/.env`.

Langfuse cloud or self-hosted:

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=YOUR_PUBLIC_KEY
LANGFUSE_SECRET_KEY=YOUR_SECRET_KEY
LANGFUSE_HOST=https://cloud.langfuse.com
```

OpenTelemetry collector:

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OTEL_SERVICE_NAME=avaas
```

LangSmith fallback:

```env
LANGSMITH_ENABLED=true
LANGSMITH_API_KEY=YOUR_KEY
LANGSMITH_PROJECT=avaas
```

Selection order is Langfuse, then OpenTelemetry, then LangSmith, then local persisted evidence. Exporter failure must not discard validation evidence or fail the run. API keys remain backend-only.

## Start backend

```powershell
cd avass-enterprise-v3\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check:

- Health: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`

## Frontend installation and startup

In a second terminal:

```powershell
cd avaas-enterprise-v3\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Set:

```env
VITE_API_URL=http://127.0.0.1:8000/api/v1
```

Open `http://localhost:5173`.

## Test through the UI

1. Register an organization, tenant slug, owner email, and strong password.
2. Create a project.
3. Choose **Browser website**.
4. Enter a public agent UI URL.
5. Click **Discover agent**. AVaaS opens the page with Playwright and inspects visible inputs, content-editable controls, buttons, response regions, iframes, and browser errors.
6. If discovery succeeds, click **Validate**.
7. AVaaS generates bounded normal, edge, injection, and multi-turn cases using Ollama, with Gemini fallback.
8. Playwright enters prompts into the real website UI and captures output, latency, browser errors, adapter details and target evidence.
9. AVaaS evaluates deterministic rules, safety/hallucination, and business/MVP criteria when authoritative requirements exist.
10. Review run status, score, evidence and release gate.

Business/use-case fields are optional. When absent, AVaaS may infer generic scenarios from page discovery; those inferences do not become authoritative business rules.

## Website limitations

A URL alone cannot guarantee automation of every website. CAPTCHA, mandatory SSO, anti-bot systems, cross-origin iframes, canvas-only UIs, cookie overlays, and unusual multi-page workflows may require credentials, explicit selectors, recorded workflows, or transcript mode. AVaaS reports discovery limitations rather than fabricating success.

For a local/private target, `ALLOW_PRIVATE_TARGETS=false` protects against SSRF. Set it to `true` only in a controlled local environment, never on a public deployment without strict network allow-listing.

## Production checks

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m compileall app
python -m pytest -q
cd ..\frontend
npm run build
```

For production, use PostgreSQL, migrations, RLS, OIDC/SSO, a secret manager, rate limiting, a durable worker queue, TLS, exact CORS origins, egress allow-lists, monitored trace exporters, backups, and refresh-token cleanup. Do not use FastAPI in-process background tasks across multiple replicas.

## Quick restart

Terminal 1:

```powershell
ollama serve
```

Terminal 2:

```powershell
cd avaas-enterprise-v3\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --port 8000
```

Terminal 3:

```powershell
cd avaas-enterprise-v3\frontend
npm run dev
```

