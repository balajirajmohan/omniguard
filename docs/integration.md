# Wire OmniGuard → Isaac Sim (after Checkpoint A + B)

Denied commands never call the adapter move path. Only `ALLOW` invokes `IsaacAdapter.execute_move`. Containment calls `emergency_stop`.

## Current stub behavior

[`broker/isaac_adapter.py`](../broker/isaac_adapter.py) logs moves and updates in-memory robot status. Set enabled when the GPU workstation is ready:

```python
# broker/main.py
adapter = IsaacAdapter(store=store, enabled=os.getenv("OMNIGUARD_ISAAC_ENABLED") == "1")
```

Or export:

```bash
export OMNIGUARD_ISAAC_ENABLED=1
uvicorn broker.main:app --host 0.0.0.0 --port 8000
```

## What to implement on the g6e workstation

Replace the `NotImplementedError` bodies in:

1. `_send_to_isaac(command)` — drive Nova Carter to the XYZ for `command.destination_zone` (see `broker/config.py` `ZONES`).
2. `_send_estop_to_isaac(robot_id)` — zero velocity / freeze articulation.

Prefer Isaac Sim’s built-in Python scripting for the MVP. Skip ROS 2 unless the team already knows it.

## Before vs after demo on Isaac

1. **Without OmniGuard:** call the Isaac move helper directly toward `HUMAN_ZONE` (show near-miss).
2. **With OmniGuard:** send the same intent through `POST /commands/move` with stolen token + `rogue-controller` → robot never receives the move; e-stop fires instead.

## Reset

```bash
curl -X POST http://127.0.0.1:8000/demo/reset
```

Reload the warehouse scene if the twin state drifted.
