# Convenience script: starts the AVaaS API and the demo target agent
# together for local development on Windows PowerShell.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Starting demo target agent on :9000 ..."
$demo = Start-Process -PassThru -NoNewWindow python -ArgumentList "-m","uvicorn","scripts.demo_target_agent:app","--port","9000"

try {
    Write-Host "Starting AVaaS API on :8000 ..."
    python -m uvicorn avaas.main:app --app-dir src --reload --port 8000
} finally {
    Stop-Process -Id $demo.Id -Force -ErrorAction SilentlyContinue
}
