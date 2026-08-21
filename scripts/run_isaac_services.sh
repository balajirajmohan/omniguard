#!/usr/bin/env bash
# Start OmniGuard against a live Isaac bridge — does NOT start fake_robot.
# Prerequisites: Isaac warehouse_robot_demo.py already listening on :8899.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing .venv. Run: bash scripts/setup.sh" >&2
  exit 1
fi

export OMNIGUARD_ROBOT_BACKEND="${OMNIGUARD_ROBOT_BACKEND:-isaac}"
export ISAAC_BRIDGE_URL="${ISAAC_BRIDGE_URL:-http://127.0.0.1:8899}"
export OMNIGUARD_API_URL="${OMNIGUARD_API_URL:-http://127.0.0.1:8000}"
export LLM_PROVIDER="${LLM_PROVIDER:-fallback}"

if ! curl -sf "${ISAAC_BRIDGE_URL%/}/health" >/dev/null 2>&1; then
  echo "WARNING: Isaac bridge at ${ISAAC_BRIDGE_URL}/health did not respond." >&2
  echo "Launch isaac/warehouse_robot_demo.py from a DCV terminal first." >&2
fi

echo "Starting backend :8000 (robot_backend=${OMNIGUARD_ROBOT_BACKEND})"
nohup "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
  > logs/backend-isaac.log 2>&1 < /dev/null &
echo $! > logs/backend-isaac.pid

echo "Starting dashboard :8501"
nohup env OMNIGUARD_API_URL="$OMNIGUARD_API_URL" \
  "$PY" -m streamlit run dashboard/app.py \
  --server.address 127.0.0.1 --server.port 8501 --server.headless true \
  > logs/dashboard-isaac.log 2>&1 < /dev/null &
echo $! > logs/dashboard-isaac.pid

sleep 2
curl -sf http://127.0.0.1:8000/health | "$PY" -m json.tool || {
  echo "Backend health failed — see logs/backend-isaac.log" >&2
  exit 1
}
curl -sf http://127.0.0.1:8501/_stcore/health >/dev/null || {
  echo "Dashboard health failed — see logs/dashboard-isaac.log" >&2
  exit 1
}

echo "Isaac-mode OmniGuard ready."
echo "  API:       http://127.0.0.1:8000/docs"
echo "  Dashboard: http://127.0.0.1:8501"
echo "  From Mac:  see docs/MAC_ACCESS.md (SSM port-forward 8501)"
echo "PIDs in logs/*.pid — stop with: kill \$(cat logs/backend-isaac.pid logs/dashboard-isaac.pid)"
