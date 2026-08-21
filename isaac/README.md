# Isaac Sim helpers (GPU day)

## Proven path (AWS Isaac Sim 6.0.1 / L40S)

| File | Role |
|------|------|
| `command_bridge.py` | In-process HTTP server (`:8899`) — `GET /health`, `POST /move`, `POST /stop` |
| `warehouse_robot_demo.py` | Warehouse + Nova Carter; kinematic move toward targets |

Nova Carter asset (Isaac 6.0.1):

```text
/Isaac/Robots/NVIDIA/NovaCarter/nova_carter.usd
```

### Order of operations

1. One Isaac GUI only (close duplicates).
2. From a **DCV** terminal with `DISPLAY` set:

```bash
/opt/IsaacSim/python.sh /path/to/omniguard/isaac/warehouse_robot_demo.py
# wait for: OmniGuard Isaac bridge listening on :8899
```

3. Start OmniGuard **without** the fake robot:

```bash
bash scripts/run_isaac_services.sh
```

4. Operate from Mac browser via SSM: [docs/MAC_ACCESS.md](../docs/MAC_ACCESS.md)

Do **not** run `scripts/run_demo.sh` for the final Isaac demo — it starts `fake_robot.py`.

## Laptop poll contract (optional)

[`simulator/isaac_bridge.py`](../simulator/isaac_bridge.py) mirrors `fake_robot.py` for poll/telemetry. The proven push path uses `OMNIGUARD_ROBOT_BACKEND=isaac` → Srikanth's `IsaacRobotController` against `:8899`.
