#!/usr/bin/env bash
# Srikanth's JWT broker path (port 8001) — does not replace the primary :8000 demo.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export OMNIGUARD_ROBOT_BACKEND="${OMNIGUARD_ROBOT_BACKEND:-mock}"
echo "JWT broker on http://127.0.0.1:8001  (docs: /docs)"
echo "Clients: BROKER_URL=http://127.0.0.1:8001 python scripts/normal_client.py"
exec uvicorn broker.main:app --host 127.0.0.1 --port 8001 --reload
