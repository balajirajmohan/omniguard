"""Standalone Isaac Sim script for OmniGuard's mobile manipulator.

Loads a bundled warehouse and the Clearpath RidgebackFranka mobile manipulator.
It drives the robot root to whatever (x, y, speed) target the OmniGuard broker
last approved via the CommandBridge HTTP server.

The previous Nova Carter path was verified on AWS Isaac Sim 6.0.1. This bundled
RidgebackFranka path must be smoke-tested on that GPU host before claiming the
same runtime status. OmniGuard exposes base MOVE/STOP plus bridge-local arm
preset, joint and gripper commands for direct curl testing.

Movement is kinematic (capped step toward target) for demo reliability — not a
validated fleet controller. Asset paths can still shift between Isaac releases.

Run on the GPU host from a DCV terminal (needs DISPLAY), with Isaac's Python:
    /opt/IsaacSim/python.sh /home/ubuntu/omniguard/isaac/warehouse_robot_demo.py

Do not start a second Isaac GUI while this process owns the scene/bridge.
"""
import math
import sys
from pathlib import Path

OMNIGUARD_ROOT = Path(__file__).resolve().parents[1]
if str(OMNIGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(OMNIGUARD_ROOT))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False})

# Everything below must be imported AFTER SimulationApp exists — Isaac Sim's
# omniverse/kit modules aren't available until the app object initializes them.
import carb  # noqa: E402
import numpy as np  # noqa: E402
from backend.zones import TELEOP_ZONES  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.utils.stage import add_reference_to_stage  # noqa: E402
from isaacsim.storage.native import get_assets_root_path  # noqa: E402

from command_bridge import CommandBridge  # noqa: E402
from demo_geometry import snap_heading_degrees, third_person_camera_eye  # noqa: E402
from mobile_manipulator import (  # noqa: E402
    MobileManipulatorAssemblyError,
    build_mobile_manipulator,
)
from zone_visuals import add_zone_visuals  # noqa: E402

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
FOLLOW_CAMERA_PATH = "/World/OmniGuardFollowCamera"
FOLLOW_CAMERA_LOOK_AT_HEIGHT = 0.9
ROBOT_FORWARD_YAW_OFFSET_DEGREES = 0.0

ARM_PRESETS_DEGREES = {
    "stow": {
        "panda_joint1": 0.0,
        "panda_joint2": -45.0,
        "panda_joint3": 0.0,
        "panda_joint4": -125.0,
        "panda_joint5": 0.0,
        "panda_joint6": 90.0,
        "panda_joint7": 45.0,
    },
    "carry": {
        "panda_joint1": 0.0,
        "panda_joint2": -55.0,
        "panda_joint3": 0.0,
        "panda_joint4": -100.0,
        "panda_joint5": 0.0,
        "panda_joint6": 80.0,
        "panda_joint7": 45.0,
    },
    "reach": {
        "panda_joint1": 0.0,
        "panda_joint2": -35.0,
        "panda_joint3": 0.0,
        "panda_joint4": -90.0,
        "panda_joint5": 0.0,
        "panda_joint6": 60.0,
        "panda_joint7": 20.0,
    },
    "inspect": {
        "panda_joint1": 25.0,
        "panda_joint2": -40.0,
        "panda_joint3": 0.0,
        "panda_joint4": -75.0,
        "panda_joint5": 0.0,
        "panda_joint6": 75.0,
        "panda_joint7": 45.0,
    },
}

GRIPPER_TARGETS = {
    "open": 0.04,
    "close": 0.0,
}
GRIPPER_JOINT_CANDIDATES = (
    "panda_finger_joint1",
    "panda_finger_joint2",
    "finger_joint1",
    "finger_joint2",
    "left_finger_joint",
    "right_finger_joint",
)


def main():
    assets_root_path = get_assets_root_path()
    if assets_root_path is None:
        carb.log_error("Could not locate Isaac Sim assets root path (Nucleus). Check your asset config.")
        simulation_app.close()
        return

    world = World(stage_units_in_meters=1.0)

    warehouse_usd = assets_root_path + "/Isaac/Environments/Simple_Warehouse/warehouse.usd"
    add_reference_to_stage(usd_path=warehouse_usd, prim_path="/World/Warehouse")
    zone_layouts = add_zone_visuals(world.stage, TELEOP_ZONES, ZONE_WAYPOINTS)
    carb.log_info(
        "Added OmniGuard warehouse zone overlays: "
        + ", ".join(layout.name for layout in zone_layouts)
    )

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
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

    xform = UsdGeom.Xformable(robot_prim)
    current_yaw_degrees = 0.0

    follow_camera = UsdGeom.Camera.Define(world.stage, FOLLOW_CAMERA_PATH)
    follow_camera.CreateFocalLengthAttr(24.0)
    follow_camera.CreateHorizontalApertureAttr(22.0)
    camera_xform = UsdGeom.Xformable(follow_camera.GetPrim())
    camera_transform_op = camera_xform.AddTransformOp()

    def set_active_follow_camera() -> None:
        try:
            from omni.kit.viewport.utility import get_active_viewport  # type: ignore

            viewport = get_active_viewport()
            if viewport is None:
                carb.log_warn("No active viewport found; follow camera was created but not selected")
                return
            if hasattr(viewport, "set_active_camera"):
                viewport.set_active_camera(FOLLOW_CAMERA_PATH)
            else:
                viewport.camera_path = Sdf.Path(FOLLOW_CAMERA_PATH)
            carb.log_info(f"Viewport camera set to {FOLLOW_CAMERA_PATH}")
        except Exception as exc:  # Isaac viewport APIs differ between versions.
            carb.log_warn(f"Could not auto-select follow camera: {exc}")

    def set_follow_camera(position: np.ndarray, yaw_degrees: float) -> None:
        eye = third_person_camera_eye(
            (float(position[0]), float(position[1]), float(position[2])),
            yaw_degrees,
        )
        target = Gf.Vec3d(
            float(position[0]),
            float(position[1]),
            float(position[2]) + FOLLOW_CAMERA_LOOK_AT_HEIGHT,
        )
        eye_vec = Gf.Vec3d(*eye)
        back = (eye_vec - target).GetNormalized()
        right = Gf.Cross(Gf.Vec3d(0.0, 0.0, 1.0), back).GetNormalized()
        up = Gf.Cross(back, right).GetNormalized()
        matrix = Gf.Matrix4d(1.0)
        matrix.SetRow(0, Gf.Vec4d(right[0], right[1], right[2], 0.0))
        matrix.SetRow(1, Gf.Vec4d(up[0], up[1], up[2], 0.0))
        matrix.SetRow(2, Gf.Vec4d(back[0], back[1], back[2], 0.0))
        matrix.SetRow(3, Gf.Vec4d(eye[0], eye[1], eye[2], 1.0))
        camera_transform_op.Set(matrix)

    def normalise_name(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def iter_robot_joints():
        for prim in Usd.PrimRange(robot_prim):
            if prim.GetTypeName() in {"PhysicsRevoluteJoint", "PhysicsPrismaticJoint"}:
                yield prim

    def joint_names() -> list[str]:
        return [str(prim.GetPath()) for prim in iter_robot_joints()]

    def find_joint(name: str):
        expected = normalise_name(name)
        suffix_matches = []
        contains_matches = []
        for prim in iter_robot_joints():
            actual = normalise_name(prim.GetName())
            if actual == expected:
                return prim
            if actual.endswith(expected):
                suffix_matches.append(prim)
            elif expected in actual:
                contains_matches.append(prim)
        if suffix_matches:
            return sorted(suffix_matches, key=lambda p: str(p.GetPath()))[0]
        if contains_matches:
            return sorted(contains_matches, key=lambda p: str(p.GetPath()))[0]
        return None

    def set_joint_drive_target(joint_prim, target: float) -> None:
        drive_name = "linear" if joint_prim.GetTypeName() == "PhysicsPrismaticJoint" else "angular"
        drive = UsdPhysics.DriveAPI.Get(joint_prim, drive_name)
        if not drive:
            drive = UsdPhysics.DriveAPI.Apply(joint_prim, drive_name)
        target_attr = drive.GetTargetPositionAttr()
        if not target_attr:
            target_attr = drive.CreateTargetPositionAttr()
        target_attr.Set(float(target))

    def apply_joint_targets(targets_degrees: dict[str, float]) -> tuple[bool, list[str]]:
        missing = []
        applied = []
        for name, target in targets_degrees.items():
            joint = find_joint(name)
            if joint is None:
                missing.append(name)
                continue
            set_joint_drive_target(joint, target)
            applied.append(str(joint.GetPath()))
        if missing:
            carb.log_warn(
                "Arm command missing joints %s. Available joints: %s"
                % (", ".join(missing), "; ".join(joint_names()))
            )
        if applied:
            carb.log_info("Applied arm targets to: " + ", ".join(applied))
        return bool(applied) and not missing, missing

    def apply_gripper_action(action: str) -> tuple[bool, list[str]]:
        target = GRIPPER_TARGETS[action]
        applied = []
        # find_joint matches on suffix, so "finger_joint1" resolves to the same
        # prim as "panda_finger_joint1". Without this the drive target is set
        # twice per finger and the reported joint list double-counts them.
        for name in GRIPPER_JOINT_CANDIDATES:
            joint = find_joint(name)
            if joint is None:
                continue
            path = str(joint.GetPath())
            if path in applied:
                continue
            set_joint_drive_target(joint, target)
            applied.append(path)
        if not applied:
            carb.log_warn(
                "Gripper command could not find finger joints. Available joints: "
                + "; ".join(joint_names())
            )
            return False, []
        carb.log_info(f"Applied gripper {action} target to: " + ", ".join(applied))
        return True, applied

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

    def set_yaw(yaw_degrees: float) -> None:
        rotate_ops = [op for op in xform.GetOrderedXformOps() if op.GetOpType() == UsdGeom.XformOp.TypeRotateZ]
        target_yaw = yaw_degrees + ROBOT_FORWARD_YAW_OFFSET_DEGREES
        if rotate_ops:
            rotate_ops[0].Set(float(target_yaw))
        else:
            xform.AddRotateZOp().Set(float(target_yaw))

    set_follow_camera(get_position(), current_yaw_degrees)
    set_active_follow_camera()

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

        arm_preset = bridge.pop_arm_preset(ROBOT_ID)
        if arm_preset is not None:
            preset = arm_preset["preset"]
            ok, missing = apply_joint_targets(ARM_PRESETS_DEGREES[preset])
            if ok:
                bridge.mark_executed(
                    arm_preset.get("command_id"),
                    arm={"mode": "preset", "preset": preset},
                )
            else:
                bridge.mark_failed(
                    arm_preset.get("command_id"),
                    reason="missing joints: " + ", ".join(missing),
                )

        arm_joints = bridge.pop_arm_joints(ROBOT_ID)
        if arm_joints is not None:
            ok, missing = apply_joint_targets(arm_joints["targets_degrees"])
            if ok:
                bridge.mark_executed(
                    arm_joints.get("command_id"),
                    arm={"mode": "joints", "targets_degrees": arm_joints["targets_degrees"]},
                )
            else:
                bridge.mark_failed(
                    arm_joints.get("command_id"),
                    reason="missing joints: " + ", ".join(missing),
                )

        gripper = bridge.pop_gripper(ROBOT_ID)
        if gripper is not None:
            ok, applied = apply_gripper_action(gripper["action"])
            if ok:
                bridge.mark_executed(
                    gripper.get("command_id"),
                    gripper={"action": gripper["action"], "joints": applied},
                )
            else:
                bridge.mark_failed(gripper.get("command_id"), reason="gripper joints not found")

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
            set_follow_camera(pos, current_yaw_degrees)
            continue

        snapped_yaw = snap_heading_degrees(dx, dy)
        if snapped_yaw is not None and snapped_yaw != current_yaw_degrees:
            current_yaw_degrees = snapped_yaw
            set_yaw(current_yaw_degrees)

        dt = world.get_physics_dt() or (1.0 / 60.0)
        step = min(distance, speed * dt)
        pos[0] += dx / distance * step
        pos[1] += dy / distance * step
        set_position(pos[0], pos[1], pos[2])
        set_follow_camera(pos, current_yaw_degrees)

    bridge.stop()
    simulation_app.close()


if __name__ == "__main__":
    main()
