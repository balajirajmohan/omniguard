#!/usr/bin/env bash
# Start OmniGuard against a live Isaac bridge — does NOT start fake_robot.
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
export ISAAC_BRIDGE_TOKEN="${ISAAC_BRIDGE_TOKEN:-omniguard-bridge}"
export OMNIGUARD_API_URL="${OMNIGUARD_API_URL:-http://127.0.0.1:8000}"
export LLM_PROVIDER="${LLM_PROVIDER:-fallback}"

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :${port}" 2>/dev/null | grep -q ":${port}"
  else
    lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
  fi
}

pid_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

for port in 8000 8501; do
  if port_in_use "$port"; then
    echo "ERROR: port ${port} already has a listener. Stop it first:" >&2
    echo "  bash scripts/stop_isaac_services.sh" >&2
    exit 1
  fi
done

for name in backend-isaac dashboard-isaac; do
  pidfile="logs/${name}.pid"
  if [[ -f "$pidfile" ]]; then
    old_pid="$(cat "$pidfile" 2>/dev/null || true)"
    if pid_alive "$old_pid"; then
      echo "ERROR: stale/active PID file ${pidfile} (pid=${old_pid})." >&2
      echo "  bash scripts/stop_isaac_services.sh" >&2
      exit 1
    fi
    rm -f "$pidfile"
  fi
done

if [[ "${OMNIGUARD_ROBOT_BACKEND}" == "isaac" ]]; then
  if ! curl -sf "${ISAAC_BRIDGE_URL%/}/health" >/dev/null 2>&1; then
    echo "ERROR: Isaac bridge health failed at ${ISAAC_BRIDGE_URL}/health" >&2
    echo "Launch isaac/warehouse_robot_demo.py from a DCV terminal first." >&2
    exit 1
  fi
fi

echo "Starting backend :8000 (robot_backend=${OMNIGUARD_ROBOT_BACKEND})"
nohup env \
  OMNIGUARD_ROBOT_BACKEND="$OMNIGUARD_ROBOT_BACKEND" \
  ISAAC_BRIDGE_URL="$ISAAC_BRIDGE_URL" \
  ISAAC_BRIDGE_TOKEN="$ISAAC_BRIDGE_TOKEN" \
  LLM_PROVIDER="$LLM_PROVIDER" \
  "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
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

echo "Isaac-mode OmniGuard ready (fake_robot NOT started)."
echo "  API:       http://127.0.0.1:8000/docs"
echo "  Dashboard: http://127.0.0.1:8501"
echo "  Stop:      bash scripts/stop_isaac_services.sh"
