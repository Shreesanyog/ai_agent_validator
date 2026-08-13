#!/usr/bin/env bash
# Convenience script: starts the AVaaS API and the demo target agent
# together for local development on Linux/macOS.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting demo target agent on :9000 ..."
DEMO_AGENT_BUG_MODE="${DEMO_AGENT_BUG_MODE:-false}" \
  python -m uvicorn scripts.demo_target_agent:app --port 9000 &
DEMO_PID=$!

trap 'kill $DEMO_PID' EXIT

echo "Starting AVaaS API on :8000 ..."
python -m uvicorn avaas.main:app --app-dir src --reload --port 8000
