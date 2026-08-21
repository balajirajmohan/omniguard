# OmniGuard alignment notes

Derived from the 21 Aug 2026 chat-history / code-alignment review, the 22-hour runbook,
and the GPT troubleshooting / agentic-AI handoff (commit `35a5f90` baseline).

## Principle

**Keep Srikanth's working JWT + Isaac stack. Make the runbook/starter kit the primary event demo.**

| Layer | Owner / source | Role now |
|-------|----------------|----------|
| `backend/` | Runbook + starter kit | Primary `:8000` API, scenarios, IsolationForest, incident AI |
| `broker/` | Srikanth | Preserved JWT `/token`+`/command` on `:8001`, policy, state, robot_adapter |
| `isaac/` | Srikanth (+ live 6.0.1 patch) | `command_bridge.py`, `warehouse_robot_demo.py` (NVIDIA/NovaCarter path) |
| `infra/` | Srikanth (+ Marketplace terraform) | GPU provisioning options |
| `simulator/` | Starter kit | Polling fake robot (laptop); optional poll bridge |
| `dashboard/` | Starter kit UI | Four buttons + scenario library against `backend` |

Dead leftovers from the pre-merge Cursor path (`broker/store.py`, `broker/isaac_adapter.py`, `broker/config.py`, `clients/`) stay **removed**.

## Best-judgment wiring

1. Laptop / CI → `bash scripts/run_demo.sh` (backend + fake_robot + dashboard).
2. GPU day → Isaac `warehouse_robot_demo.py` on `:8899`, then `bash scripts/run_isaac_services.sh` (no fake robot).
3. Primary backend optionally **pushes** via Srikanth's Isaac adapter while still filling the poll queue.
4. Mac operators → SSM port-forward to `:8501` ([MAC_ACCESS.md](MAC_ACCESS.md)).
5. JWT broker remains runnable for deep policy demos without conflicting with `:8000`.

## Handoff corrections already applied

- Nova Carter USD path for Isaac Sim 6.0.1 under `Robots/NVIDIA/`.
- Explicit Isaac service script (fake robot ambiguity removed).
- Scenario catalog API + browser scenario runner.
- LLM provider disclosure + OpenAI/Bedrock optional path with deterministic fallback.
- Honest README status (control path proven ≠ judge product complete until Mac UI + scenarios rehearsed).

## Do not build during the event

Kubernetes, Kafka, ROS (unless already working), custom warehouse, local LLM, multi-robot fleet, production IAM.
