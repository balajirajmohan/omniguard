#!/usr/bin/env bash
# GPU-host bootstrap for OmniGuard (AWS Isaac workstation).
# Use bash explicitly: bash scripts/getomni.sh
set -Eeuo pipefail

trap 'echo "getomni.sh failed at line $LINENO" >&2' ERR

if [[ -z "${BASH_VERSION:-}" ]]; then
  echo "Run with bash: bash scripts/getomni.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== host =="
whoami
hostname
nvidia-smi -L 2>/dev/null || echo "nvidia-smi unavailable"
python3 --version

ISAAC_ROOT="${ISAAC_ROOT:-/opt/IsaacSim}"
if [[ -x "${ISAAC_ROOT}/python.sh" ]]; then
  echo "Isaac launcher: ${ISAAC_ROOT}/python.sh"
else
  echo "WARNING: ${ISAAC_ROOT}/python.sh not found"
fi

echo "== python env =="
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m ensurepip --upgrade >/dev/null 2>&1 || true
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "== tests =="
pytest -q

echo "OmniGuard environment ready at commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Next:"
echo "  Laptop/mock:  bash scripts/run_demo.sh"
echo "  Isaac path:   launch isaac/warehouse_robot_demo.py in DCV, then bash scripts/run_isaac_services.sh"
