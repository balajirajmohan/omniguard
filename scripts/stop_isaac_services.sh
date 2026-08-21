#!/usr/bin/env bash
# Stop OmniGuard backend/dashboard started by run_isaac_services.sh.
# Never terminates the Isaac GUI unless STOP_ISAAC_GUI=1 is set explicitly.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

stop_pidfile() {
  local pidfile="$1"
  local label="$2"
  if [[ ! -f "$pidfile" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "Stopping ${label} pid=${pid}"
    kill -TERM "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  fi
  rm -f "$pidfile"
}

stop_pidfile logs/backend-isaac.pid backend
stop_pidfile logs/dashboard-isaac.pid dashboard

# Also clear accidental listeners on OmniGuard ports (not Isaac :8899).
for port in 8000 8501; do
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:${port} -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "${pids}" ]]; then
      echo "Clearing leftover listeners on :${port}: ${pids}"
      # shellcheck disable=SC2086
      kill -TERM ${pids} 2>/dev/null || true
    fi
  fi
done

if [[ "${STOP_ISAAC_GUI:-0}" == "1" ]]; then
  echo "STOP_ISAAC_GUI=1 set — refusing automatic GUI kill for safety."
  echo "Stop Isaac manually from the DCV desktop (File → Exit)."
fi

echo "OmniGuard Isaac services stopped. Bridge/GUI left running."
