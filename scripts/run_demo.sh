#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
mkdir -p logs

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "${ROBOT_PID:-}" ]]; then kill "$ROBOT_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

# Bind localhost for the laptop demo (Procfile uses 0.0.0.0 for Codespaces only).
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 >logs/backend.log 2>&1 &
BACKEND_PID=$!

ready=false
for _ in {1..30}; do
  if python -c "import requests; requests.get('http://127.0.0.1:8000/health', timeout=1).raise_for_status()" 2>/dev/null; then
    ready=true
    break
  fi
  sleep 1
done

if [[ "$ready" != true ]]; then
  echo "Backend failed to become healthy; see logs/backend.log" >&2
  exit 1
fi

python simulator/fake_robot.py >logs/fake_robot.log 2>&1 &
ROBOT_PID=$!

echo "OmniGuard dashboard: http://127.0.0.1:8501"
echo "API docs:            http://127.0.0.1:8000/docs"
echo "Note: local-demo credential path — keep on private network only."
python -m streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1
