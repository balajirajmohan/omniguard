# OmniGuard alignment notes

Derived from the 21 Aug 2026 chat-history / code-alignment review (commit `3bd322e`) and the official 22-hour runbook.

## What was wrong on `main`

After merging PR #1 (devcontainer) and PR #2 (`feature/omniguard-local`), the tree contained **two incompatible APIs**:

| Stale path | Live path (post-merge) |
|------------|------------------------|
| `clients/` → `/tokens/demo-agent`, `/commands/move` | `scripts/` → `/token`, `/command` |
| `broker/store.py`, `broker/isaac_adapter.py` | Broken imports; dead code |
| Docs referencing `OMNIGUARD_ISAAC_ENABLED` | Code used `OMNIGUARD_ROBOT_BACKEND` |

Readiness was assessed ~57%: strong Zero-Trust core, missing IsolationForest + incident LLM + protection OFF/ON, Isaac unverified.

## What this branch does

1. **Single source of truth** matching the runbook + starter kit:
   - `backend/` (policy, anomaly, incident_ai, FastAPI `/api/*`)
   - `dashboard/` four buttons
   - `simulator/fake_robot.py` + `simulator/isaac_bridge.py`
   - `tests/test_api.py`
2. **Removes** `broker/` and `clients/` duplicate implementations.
3. **Adds** IsolationForest risk scoring, HOLD band, Bedrock/fallback incident explanation, protection OFF/ON demo.
4. **Keeps** `isaac/` GPU helpers and `infra/terraform/` Marketplace workstation path.
5. **Replaces** docs/run commands with the runbook contract.

## Prefer

- Starter/runbook HTTP polling contract over push-only adapters for the event.
- Marketplace `infra/terraform` (g6e + DCV) when organizers allocate AWS; keep lightweight scene on `g6e.xlarge` if that is what you get.
- Fake robot until Isaac move/stop is proven on GPU.

## Do not build during the event

Kubernetes, Kafka, ROS (unless already working), custom warehouse, local LLM, multi-robot fleet, production IAM.
