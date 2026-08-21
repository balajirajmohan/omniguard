# Isaac Sim helpers (GPU day) — Srikanth + runbook

## Prefer for the event

[`simulator/isaac_bridge.py`](../simulator/isaac_bridge.py) — same poll/telemetry contract as `fake_robot.py`.

## Srikanth's preserved helpers

| File | Role |
|------|------|
| `command_bridge.py` | In-process HTTP server (`:8899`) for push moves/stops from `broker.robot_adapter` |
| `warehouse_robot_demo.py` | Warehouse + Nova Carter starter sketch (verify on GPU) |

## Order of operations

1. Laptop demo green (`bash scripts/run_demo.sh`).
2. On GPU: Isaac launches; one robot moves/stops from Python.
3. Either:
   - Implement TODOs in `simulator/isaac_bridge.py` and stop `fake_robot`, **or**
   - Start `command_bridge` inside Isaac and set `OMNIGUARD_ROBOT_BACKEND=isaac` / `ISAAC_BRIDGE_URL`.
4. Record a backup video immediately.
