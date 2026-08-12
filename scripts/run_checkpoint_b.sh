#!/usr/bin/env bash
# Run Checkpoint B demo end-to-end (broker must already be listening on :8000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
curl -s -X POST http://127.0.0.1:8000/demo/reset >/dev/null
echo "=== Normal operator ==="
"$PY" clients/normal_client.py
echo
echo "=== Attack + reuse ==="
"$PY" clients/attack_client.py --reuse
echo
echo "Demo complete. Open dashboard with: streamlit run dashboard/app.py"
