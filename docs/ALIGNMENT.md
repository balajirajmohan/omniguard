# OmniGuard alignment notes

Derived from the 21 Aug 2026 chat-history / code-alignment review and the official 22-hour runbook.

## Principle on this branch

**Keep Srikanth's working JWT + Isaac stack. Make the runbook/starter kit the primary event demo.**

| Layer | Owner / source | Role now |
|-------|----------------|----------|
| `backend/` | Runbook + starter kit | Primary `:8000` API, IsolationForest, incident AI, four-button demo |
| `broker/` | Srikanth | Preserved JWT `/token`+`/command` on `:8001`, policy, state, robot_adapter |
| `isaac/` | Srikanth | `command_bridge.py`, `warehouse_robot_demo.py` |
| `infra/` | Srikanth (+ Marketplace terraform) | GPU provisioning options |
| `simulator/` | Starter kit | Polling fake robot / Isaac bridge (shared HTTP contract) |
| `dashboard/` | Starter kit UI | Four buttons against `backend` |

Dead leftovers from the pre-merge Cursor path (`broker/store.py`, `broker/isaac_adapter.py`, `broker/config.py`, `clients/`) stay **removed** — they never imported cleanly against Srikanth's models.

## Best-judgment wiring

1. Event day → `bash scripts/run_demo.sh` (backend + fake_robot + dashboard).
2. GPU day → implement `simulator/isaac_bridge.py` TODOs **or** run Srikanth's in-process `isaac/command_bridge.py` and set `OMNIGUARD_ROBOT_BACKEND=isaac`.
3. Primary backend optionally **pushes** to Srikanth's Isaac adapter while still filling the poll queue (belt and suspenders).
4. JWT broker remains runnable for deep policy demos without conflicting with `:8000`.

## Do not build during the event

Kubernetes, Kafka, ROS (unless already working), custom warehouse, local LLM, multi-robot fleet, production IAM.
