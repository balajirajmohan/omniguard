# Isaac Sim helpers (GPU day)

Primary event integration path is **[`simulator/isaac_bridge.py`](../simulator/isaac_bridge.py)** — it uses the same poll/telemetry contract as `fake_robot.py`.

This folder keeps optional in-process helpers from earlier work:

- `command_bridge.py` — HTTP server to queue moves inside Isaac's process
- `warehouse_robot_demo.py` — starter scene/motion sketch (unverified on GPU until you run it)

## Order of operations

1. Laptop demo green (`bash scripts/run_demo.sh`).
2. On GPU: Isaac launches, warehouse loads, one robot moves/stops from Python.
3. Implement TODOs in `simulator/isaac_bridge.py`.
4. Stop `fake_robot` / remove `robot:` from Procfile so only Isaac consumes commands.
5. Record a backup video immediately.
