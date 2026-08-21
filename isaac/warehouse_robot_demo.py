"""Standalone Isaac Sim script: loads a bundled warehouse, spawns one bundled
mobile robot (Nova Carter), and drives it to whatever (x, y, speed) target the
OmniGuard broker last approved via the CommandBridge HTTP server.

Verified on AWS Isaac Sim 6.0.1 (L40S): warehouse loads, Nova Carter moves/stops
via CommandBridge :8899 when OmniGuard sets OMNIGUARD_ROBOT_BACKEND=isaac.

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

ROBOT_ID = "robot-01"
ROBOT_PRIM_PATH = "/World/NovaCarter"

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

    # Isaac Sim 6.0.1 catalogs Nova Carter under Robots/NVIDIA/ (not Robots/NovaCarter).
    nova_carter_usd = (
        assets_root_path + "/Isaac/Robots/NVIDIA/NovaCarter/nova_carter.usd"
    )
    add_reference_to_stage(usd_path=nova_carter_usd, prim_path=ROBOT_PRIM_PATH)

    world.reset()

    robot_prim = world.stage.GetPrimAtPath(ROBOT_PRIM_PATH)
    import omni.usd
    from pxr import Gf, UsdGeom

    xform = UsdGeom.Xformable(robot_prim)

    def get_position() -> np.ndarray:
        matrix = np.array(omni.usd.get_world_transform_matrix(robot_prim))
        return np.array([matrix[3][0], matrix[3][1], matrix[3][2]])

    def set_position(x: float, y: float, z: float):
        translate_ops = [op for op in xform.GetOrderedXformOps() if op.GetOpType() == UsdGeom.XformOp.TypeTranslate]
        if translate_ops:
            translate_ops[0].Set(Gf.Vec3d(x, y, z))
        else:
            xform.AddTranslateOp().Set(Gf.Vec3d(x, y, z))

    bridge = CommandBridge(port=8899)
    bridge.start()
    print("OmniGuard Isaac bridge listening on :8899")

    target = None  # (x, y, speed)

    while simulation_app.is_running():
        world.step(render=True)

        if bridge.pop_stop(ROBOT_ID):
            target = None
            print("EMERGENCY STOP received for", ROBOT_ID)
            continue

        move = bridge.pop_move(ROBOT_ID)
        if move is not None:
            target = (move["x"], move["y"], min(move["speed"], MAX_STEP_SPEED))

        if target is None:
            continue

        pos = get_position()
        tx, ty, speed = target
        dx, dy = tx - pos[0], ty - pos[1]
        distance = math.hypot(dx, dy)
        if distance < 0.05:
            target = None
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
