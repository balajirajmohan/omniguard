# Isaac Sim helpers (GPU day)

## Mobile-manipulator path (Isaac Sim 6.0.1 / AWS L40S)

> **Validation status:** the former Nova Carter path was proven on the AWS host.
> The new composite below is implemented but still needs the GPU smoke test in
> [docs/isaac-setup.md](../docs/isaac-setup.md) before it is called proven.

| File                      | Role                                                                         |
| ------------------------- | ---------------------------------------------------------------------------- |
| `command_bridge.py`       | In-process HTTP server (`:8899`) — `GET /health`, `POST /move`, `POST /stop` |
| `mobile_manipulator.py`   | Loads the bundled Clearpath Ridgeback + Franka mobile manipulator            |
| `warehouse_robot_demo.py` | Warehouse + composite robot; kinematic base MOVE/STOP                        |

Default Isaac Sim 6.0.1 asset:

```text
/Isaac/Robots/Clearpath/RidgebackFranka/ridgeback_franka.usd
```

This bundled catalog robot is preferred because it is already a coherent mobile
manipulator: wheeled Ridgeback base plus Franka/Panda-style arm and end-effector.
This phase does **not** add arm trajectory, IK, grasp, or gripper commands to the
broker; OmniGuard still exposes only base MOVE and emergency STOP.

Useful catalog alternatives:

```text
/Isaac/Robots/Clearpath/RidgebackUr/ridgeback_ur5.usd       # visually close to UR-on-Ridgeback screenshots
/Isaac/Robots/BostonDynamics/spot/spot_with_arm.usd         # arm, but not wheeled
```

### Runtime tuning

Override the bundled mobile manipulator asset if needed:

```bash
export OMNIGUARD_MOBILE_MANIPULATOR_USD=/Isaac/Robots/Clearpath/RidgebackFranka/ridgeback_franka.usd
# export OMNIGUARD_MOBILE_MANIPULATOR_USD=/Isaac/Robots/Clearpath/RidgebackUr/ridgeback_ur5.usd
```

### Legacy composite fallback

The old custom assembly path can be enabled only for experiments:

```bash
export OMNIGUARD_USE_COMPOSITE_MOBILE_MANIPULATOR=true
```

Mount prims are discovered by name and validated before assembly. If the catalog
asset hierarchy differs on the GPU image for the legacy composite path, set a
relative path below the corresponding robot root (or an absolute stage path):

```bash
export OMNIGUARD_IWHUB_ARM_MOUNT=base_link
export OMNIGUARD_UR10E_BASE_MOUNT=base_link
export OMNIGUARD_UR10E_TOOL_MOUNT=ee_link
export OMNIGUARD_ROBOTIQ_BASE_MOUNT=robotiq_base_link
```

Offsets are `x,y,z` metres and XYZ Euler degrees. Defaults are conservative,
but the iw.hub top height and flange orientation must be visually verified:

```bash
export OMNIGUARD_ARM_MOUNT_TRANSLATION=0,0,0.62
export OMNIGUARD_ARM_MOUNT_ROTATION_DEGREES=0,0,0
export OMNIGUARD_GRIPPER_MOUNT_TRANSLATION=0,0,0
export OMNIGUARD_GRIPPER_MOUNT_ROTATION_DEGREES=0,0,0
export OMNIGUARD_UR10E_STOW_DEGREES=0,-90,90,-90,-90,0
```

Legacy component asset paths can also be overridden with `OMNIGUARD_IWHUB_USD`,
`OMNIGUARD_UR10E_USD`, and `OMNIGUARD_ROBOTIQ_2F140_USD`. The process fails
closed with a prim diagnostic if required assets, mounts, or UR10e joints cannot
be found.

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

### GPU acceptance checks

Before demo use, confirm the Ridgeback base, arm, and end-effector appear as one
coherent robot, MOVE carries the entire asset, and STOP halts the current
waypoint. If using the legacy composite path and a mount cannot be discovered,
copy the available prim path from the emitted diagnostic into the relevant
override above.

## Laptop poll contract (optional)

[`simulator/isaac_bridge.py`](../simulator/isaac_bridge.py) mirrors `fake_robot.py` for poll/telemetry. The proven push path uses `OMNIGUARD_ROBOT_BACKEND=isaac` → Srikanth's `IsaacRobotController` against `:8899`.
