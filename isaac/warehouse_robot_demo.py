"""Standalone Isaac Sim script for OmniGuard's mobile manipulator.

Loads a bundled warehouse and assembles an Idealworks iw.hub, UR10e and
Robotiq 2F-140. It drives the composite robot to whatever (x, y, speed) target
the OmniGuard broker last approved via the CommandBridge HTTP server.

The previous Nova Carter path was verified on AWS Isaac Sim 6.0.1. This new
composite asset must be smoke-tested on that GPU host before claiming the same
runtime status. The arm remains stowed and the gripper remains open in this
phase; OmniGuard exposes only base MOVE and emergency STOP.

Movement is kinematic (capped step toward target) for demo reliability — not a
validated fleet controller. Asset paths can still shift between Isaac releases.

Run on the GPU host from a DCV terminal (needs DISPLAY), with Isaac's Python:
    /opt/IsaacSim/python.sh /home/ubuntu/omniguard/isaac/warehouse_robot_demo.py

Do not start a second Isaac GUI while this process owns the scene/bridge.
"""
import math

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False})

# Everything below must be imported AFTER SimulationApp exists — Isaac Sim's
# omniverse/kit modules aren't available until the app object initializes them.
import carb  # noqa: E402
import numpy as np  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
from isaacsim.storage.native import get_assets_root_path  # noqa: E402

from command_bridge import CommandBridge  # noqa: E402
from mobile_manipulator import (  # noqa: E402
    MobileManipulatorAssemblyError,
    build_mobile_manipulator,
)

ROBOT_ID = "robot-01"

# Zones used by backend/actuation.py and the four-button demo.
ZONE_WAYPOINTS = {
    "SAFE_ZONE_A": (0.0, 0.0),
    "SAFE_ZONE_B": (10.0, 4.0),
    "ZONE_A": (0.0, 0.0),
    "ZONE_B": (10.0, 4.0),
    "RESTRICTED_ZONE": (6.0, 8.0),
    "HUMAN_ZONE": (6.0, 8.0),
}

MAX_STEP_SPEED = 2.0  # m/s safety cap regardless of what a command requests


def main():
    assets_root_path = get_assets_root_path()
    if assets_root_path is None:
        carb.log_error("Could not locate Isaac Sim assets root path (Nucleus). Check your asset config.")
        simulation_app.close()
        return

    world = World(stage_units_in_meters=1.0)

    warehouse_usd = assets_root_path + "/Isaac/Environments/Simple_Warehouse/warehouse.usd"
    add_reference_to_stage(usd_path=warehouse_usd, prim_path="/World/Warehouse")

    try:
        robot = build_mobile_manipulator(
            world.stage,
            assets_root_path,
            log=carb.log_info,
        )
    except (MobileManipulatorAssemblyError, ValueError) as exc:
        carb.log_error(f"Could not build OmniGuard mobile manipulator: {exc}")
        simulation_app.close()
        return

    world.reset()

    robot_prim = world.stage.GetPrimAtPath(robot.root_prim_path)
    if not robot_prim.IsValid():
        carb.log_error(f"Composite robot root is invalid: {robot.root_prim_path}")
        simulation_app.close()
        return
    import omni.usd
    from pxr import Gf, UsdGeom

    xform = UsdGeom.Xformable(robot_prim)

    def get_position() -> np.ndarray:
        matrix = np.array(omni.usd.get_world_transform_matrix(robot_prim))
        return np.array([matrix[3][0], matrix[3][1], matrix[3][2]])

    def set_position(x: float, y: float, z: float):
        translate_ops = [op for op in xform.GetOrderedXformOps() if op.GetOpType() == UsdGeom.XformOp.TypeTranslate]
        if translate_ops:
            precision = translate_ops[0].GetPrecision()
            vector = Gf.Vec3f(x, y, z) if precision == UsdGeom.XformOp.PrecisionFloat else Gf.Vec3d(x, y, z)
            translate_ops[0].Set(vector)
        else:
            xform.AddTranslateOp().Set(Gf.Vec3d(x, y, z))

    bridge = CommandBridge(port=8899)
    bridge.start()
    print(f"OmniGuard Isaac bridge listening on {bridge.host}:{bridge.port}")

    target = None  # (x, y, speed)

    while simulation_app.is_running():
        world.step(render=True)
        pos = get_position()
        bridge.update_state(
            position={"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])},
            speed=float(target[2]) if target else 0.0,
            motion_state="MOVING" if target else "IDLE",
            target={"x": target[0], "y": target[1]} if target else None,
        )

        stop = bridge.pop_stop(ROBOT_ID)
        if stop:
            target = None
            bridge.mark_executed(
                stop.get("command_id"),
                motion_state="STOPPED",
                speed=0.0,
                target=None,
            )
            print("EMERGENCY STOP executed for", ROBOT_ID)
            continue

        move = bridge.pop_move(ROBOT_ID)
        if move is not None:
            target = (move["x"], move["y"], min(move["speed"], MAX_STEP_SPEED))
            bridge.mark_executed(
                move.get("command_id"),
                motion_state="MOVING",
                speed=float(target[2]),
                target={"x": target[0], "y": target[1]},
            )

        if target is None:
            continue

        pos = get_position()
        tx, ty, speed = target
        dx, dy = tx - pos[0], ty - pos[1]
        distance = math.hypot(dx, dy)
        if distance < 0.05:
            target = None
            bridge.update_state(motion_state="IDLE", speed=0.0, target=None)
            continue

        dt = world.get_physics_dt() or (1.0 / 60.0)
        step = min(distance, speed * dt)
        pos[0] += dx / distance * step
        pos[1] += dy / distance * step
        set_position(pos[0], pos[1], pos[2])

    bridge.stop()
    simulation_app.close()


if __name__ == "__main__":
    main()
