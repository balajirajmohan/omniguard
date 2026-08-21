"""Build the OmniGuard mobile manipulator from Isaac Sim 6.0.1 assets.

This module intentionally has no Isaac Sim imports at module load time.  The
standalone application imports it after ``SimulationApp`` has initialized Kit,
while laptop tests can still exercise the path/configuration helpers.

The assembled robot is:

    Idealworks iw.hub -> Universal Robots UR10e -> Robotiq 2F-140

Robot Assembler creates the simulated fixed joints.  A shared parent Xform is
also used as the kinematic demo root so the three referenced assets remain
visually coherent while OmniGuard's existing waypoint demo moves the platform.
The arm is held at a conservative home target and the gripper is held open;
this phase deliberately exposes no manipulation command surface.
"""

from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable, TypeAlias, cast
from urllib.parse import urlparse


MOBILE_MANIPULATOR_ROOT_PRIM_PATH = "/World/OmniGuardMobileManipulator"
IWHUB_PRIM_PATH = f"{MOBILE_MANIPULATOR_ROOT_PRIM_PATH}/Base"
UR10E_PRIM_PATH = f"{MOBILE_MANIPULATOR_ROOT_PRIM_PATH}/Arm"
ROBOTIQ_2F140_PRIM_PATH = f"{MOBILE_MANIPULATOR_ROOT_PRIM_PATH}/Gripper"

IWHUB_USD_PATH = "/Isaac/Robots/Idealworks/iwhub/iw_hub.usd"
UR10E_USD_PATH = "/Isaac/Robots/UniversalRobots/ur10e/ur10e.usd"
ROBOTIQ_2F140_USD_PATH = (
    "/Isaac/Robots/Robotiq/2F-140/Robotiq_2F_140_config.usd"
)

UR10E_JOINT_NAMES = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)

IWHUB_ARM_MOUNT_CANDIDATES = (
    "payload_mount",
    "top_mount",
    "mount",
    "base_link",
    "chassis_link",
    "chassis",
)
UR10E_BASE_MOUNT_CANDIDATES = ("base_link", "base")
UR10E_TOOL_MOUNT_CANDIDATES = (
    "tool0",
    "ee_link",
    "flange",
    "wrist_3_link",
)
ROBOTIQ_BASE_MOUNT_CANDIDATES = (
    "robotiq_base_link",
    "robotiq_arg2f_base_link",
    "robotiq_2f_140_base_link",
    "base_link",
    "base",
)
ROBOTIQ_OPEN_JOINT_CANDIDATES = (
    "finger_joint",
    "left_outer_knuckle_joint",
    "robotiq_2f_140_left_driver_joint",
)

Vector3: TypeAlias = tuple[float, float, float]
JointVector6: TypeAlias = tuple[float, float, float, float, float, float]


class MobileManipulatorAssemblyError(RuntimeError):
    """Raised when an asset cannot be loaded or safely assembled."""


def parse_numeric_tuple(
    value: str,
    *,
    length: int,
    setting_name: str,
) -> tuple[float, ...]:
    """Parse a comma-separated numeric environment setting."""

    parts = [part.strip() for part in value.split(",")]
    if len(parts) != length:
        raise ValueError(
            f"{setting_name} must contain {length} comma-separated values; "
            f"received {value!r}"
        )
    try:
        parsed = tuple(float(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{setting_name} contains a non-numeric value: {value!r}") from exc
    if not all(math.isfinite(item) for item in parsed):
        raise ValueError(f"{setting_name} must contain only finite values: {value!r}")
    return parsed


def resolve_asset_path(assets_root_path: str, configured_path: str) -> str:
    """Resolve an Isaac catalog path while preserving URI/local overrides."""

    configured_path = configured_path.strip()
    if not configured_path:
        raise ValueError("Isaac asset path cannot be empty")

    parsed = urlparse(configured_path)
    if parsed.scheme:
        return configured_path
    if configured_path.startswith("/Isaac/"):
        return f"{assets_root_path.rstrip('/')}{configured_path}"
    if os.path.isabs(configured_path):
        return configured_path
    return f"{assets_root_path.rstrip('/')}/{configured_path.lstrip('/')}"


@dataclass(frozen=True)
class MountOffset:
    translation: Vector3
    rotation_degrees: Vector3


@dataclass(frozen=True)
class MobileManipulatorConfig:
    """Runtime-tunable asset, attachment and safe-pose configuration."""

    iwhub_usd: str = IWHUB_USD_PATH
    ur10e_usd: str = UR10E_USD_PATH
    robotiq_usd: str = ROBOTIQ_2F140_USD_PATH
    iwhub_arm_mount: str | None = None
    ur10e_base_mount: str | None = None
    ur10e_tool_mount: str | None = None
    robotiq_base_mount: str | None = None
    arm_offset: MountOffset = MountOffset(
        translation=(0.0, 0.0, 0.62),
        rotation_degrees=(0.0, 0.0, 0.0),
    )
    gripper_offset: MountOffset = MountOffset(
        translation=(0.0, 0.0, 0.0),
        rotation_degrees=(0.0, 0.0, 0.0),
    )
    ur10e_stow_degrees: JointVector6 = (
        0.0,
        -90.0,
        90.0,
        -90.0,
        -90.0,
        0.0,
    )
    asset_load_timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "MobileManipulatorConfig":
        arm_translation = parse_numeric_tuple(
            os.getenv("OMNIGUARD_ARM_MOUNT_TRANSLATION", "0,0,0.62"),
            length=3,
            setting_name="OMNIGUARD_ARM_MOUNT_TRANSLATION",
        )
        arm_rotation = parse_numeric_tuple(
            os.getenv("OMNIGUARD_ARM_MOUNT_ROTATION_DEGREES", "0,0,0"),
            length=3,
            setting_name="OMNIGUARD_ARM_MOUNT_ROTATION_DEGREES",
        )
        gripper_translation = parse_numeric_tuple(
            os.getenv("OMNIGUARD_GRIPPER_MOUNT_TRANSLATION", "0,0,0"),
            length=3,
            setting_name="OMNIGUARD_GRIPPER_MOUNT_TRANSLATION",
        )
        gripper_rotation = parse_numeric_tuple(
            os.getenv("OMNIGUARD_GRIPPER_MOUNT_ROTATION_DEGREES", "0,0,0"),
            length=3,
            setting_name="OMNIGUARD_GRIPPER_MOUNT_ROTATION_DEGREES",
        )
        stow_degrees = parse_numeric_tuple(
            os.getenv("OMNIGUARD_UR10E_STOW_DEGREES", "0,-90,90,-90,-90,0"),
            length=6,
            setting_name="OMNIGUARD_UR10E_STOW_DEGREES",
        )

        timeout_raw = os.getenv("OMNIGUARD_ASSET_LOAD_TIMEOUT_SECONDS", "60")
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ValueError(
                "OMNIGUARD_ASSET_LOAD_TIMEOUT_SECONDS must be numeric"
            ) from exc
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("OMNIGUARD_ASSET_LOAD_TIMEOUT_SECONDS must be positive")

        return cls(
            iwhub_usd=os.getenv("OMNIGUARD_IWHUB_USD", IWHUB_USD_PATH),
            ur10e_usd=os.getenv("OMNIGUARD_UR10E_USD", UR10E_USD_PATH),
            robotiq_usd=os.getenv("OMNIGUARD_ROBOTIQ_2F140_USD", ROBOTIQ_2F140_USD_PATH),
            iwhub_arm_mount=os.getenv("OMNIGUARD_IWHUB_ARM_MOUNT") or None,
            ur10e_base_mount=os.getenv("OMNIGUARD_UR10E_BASE_MOUNT") or None,
            ur10e_tool_mount=os.getenv("OMNIGUARD_UR10E_TOOL_MOUNT") or None,
            robotiq_base_mount=os.getenv("OMNIGUARD_ROBOTIQ_BASE_MOUNT") or None,
            arm_offset=MountOffset(
                translation=cast(Vector3, arm_translation),
                rotation_degrees=cast(Vector3, arm_rotation),
            ),
            gripper_offset=MountOffset(
                translation=cast(Vector3, gripper_translation),
                rotation_degrees=cast(Vector3, gripper_rotation),
            ),
            ur10e_stow_degrees=cast(JointVector6, stow_degrees),
            asset_load_timeout_seconds=timeout,
        )


@dataclass(frozen=True)
class MobileManipulatorAssembly:
    root_prim_path: str
    base_prim_path: str
    arm_prim_path: str
    gripper_prim_path: str
    base_arm_mount_path: str
    arm_base_mount_path: str
    arm_tool_mount_path: str
    gripper_base_mount_path: str


def _normalise_prim_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _prim_diagnostic(prim) -> str:
    schemas = ",".join(prim.GetAppliedSchemas()) or "none"
    return f"{prim.GetPath()} (schemas={schemas})"


def _descendants(root) -> list:
    from pxr import Usd

    prims = list(Usd.PrimRange(root))
    return prims[1:]


def _resolve_mount_path(
    stage,
    *,
    robot_root_path: str,
    override: str | None,
    candidates: Iterable[str],
    role: str,
) -> str:
    root = stage.GetPrimAtPath(robot_root_path)
    if not root.IsValid():
        raise MobileManipulatorAssemblyError(
            f"Cannot resolve {role}: robot prim is invalid at {robot_root_path}"
        )

    if override:
        path = (
            override
            if override.startswith("/")
            else f"{robot_root_path}/{override.lstrip('/')}"
        )
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            raise MobileManipulatorAssemblyError(
                f"Configured {role} does not exist: {path}"
            )
        return path

    descendants = _descendants(root)
    for candidate in candidates:
        expected = _normalise_prim_name(candidate)
        matches = [
            prim
            for prim in descendants
            if _normalise_prim_name(prim.GetName()) == expected
        ]
        if matches:
            # Prefer a Robot Link/Site or rigid body when duplicate leaf names
            # exist, then the shallowest deterministic path.
            def rank(prim) -> tuple[int, int, str]:
                schemas = " ".join(prim.GetAppliedSchemas()).lower()
                link_or_site = int("link" in schemas or "site" in schemas)
                rigid_body = int("rigidbody" in schemas)
                depth = str(prim.GetPath()).count("/")
                return (-(link_or_site * 2 + rigid_body), depth, str(prim.GetPath()))

            return str(sorted(matches, key=rank)[0].GetPath())

    available = ", ".join(
        _prim_diagnostic(prim)
        for prim in descendants
        if prim.GetTypeName() in {"Xform", "PhysicsRevoluteJoint", "PhysicsFixedJoint"}
    )
    if len(available) > 4000:
        available = f"{available[:4000]} ..."
    raise MobileManipulatorAssemblyError(
        f"Could not auto-detect {role} below {robot_root_path}. "
        f"Set the documented mount override. Available prims: {available or 'none'}"
    )


def _wait_for_references(
    stage,
    prim_paths: Iterable[str],
    *,
    timeout_seconds: float,
) -> None:
    import omni.kit.app

    paths = tuple(prim_paths)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        omni.kit.app.get_app().update()
        if all(
            stage.GetPrimAtPath(path).IsValid()
            and bool(stage.GetPrimAtPath(path).GetChildren())
            for path in paths
        ):
            return
        time.sleep(0.05)

    missing = [
        path
        for path in paths
        if not stage.GetPrimAtPath(path).IsValid()
        or not bool(stage.GetPrimAtPath(path).GetChildren())
    ]
    raise MobileManipulatorAssemblyError(
        "Timed out while loading Isaac robot references: " + ", ".join(missing)
    )


def _append_mount_offset(prim, offset: MountOffset, *, suffix: str) -> None:
    from pxr import Gf, UsdGeom

    rotation = (
        Gf.Rotation(Gf.Vec3d(1.0, 0.0, 0.0), offset.rotation_degrees[0])
        * Gf.Rotation(Gf.Vec3d(0.0, 1.0, 0.0), offset.rotation_degrees[1])
        * Gf.Rotation(Gf.Vec3d(0.0, 0.0, 1.0), offset.rotation_degrees[2])
    )
    transform = Gf.Transform()
    transform.SetTranslation(Gf.Vec3d(*offset.translation))
    transform.SetRotation(rotation)
    UsdGeom.Xformable(prim).AddTransformOp(
        op_suffix=f"omniguard_{suffix}"
    ).Set(transform.GetMatrix())


def _settle_kit_updates(steps: int = 4) -> None:
    import omni.kit.app

    app = omni.kit.app.get_app()
    for _ in range(steps):
        app.update()


def _enable_robot_assembler_extension() -> None:
    import omni.kit.app

    manager = omni.kit.app.get_app().get_extension_manager()
    extension_name = "isaacsim.robot_setup.assembler"
    if manager.get_enabled_extension_id(extension_name) is None:
        manager.set_extension_enabled_immediate(extension_name, True)
        _settle_kit_updates()


def _assemble_attachment(
    stage,
    *,
    base_robot_path: str,
    base_mount_path: str,
    attach_robot_path: str,
    attach_mount_path: str,
    namespace: str,
    variant_name: str,
    offset: MountOffset,
) -> None:
    _enable_robot_assembler_extension()
    from isaacsim.robot_setup.assembler import RobotAssembler

    assembler = RobotAssembler()
    try:
        assembler.begin_assembly(
            stage,
            base_robot_path,
            base_mount_path,
            attach_robot_path,
            attach_mount_path,
            namespace,
            variant_name,
        )
        attach_prim = stage.GetPrimAtPath(attach_robot_path)
        if not attach_prim.IsValid():
            raise MobileManipulatorAssemblyError(
                f"Robot Assembler invalidated attach prim {attach_robot_path}"
            )
        _append_mount_offset(attach_prim, offset, suffix=namespace.lower())
        assembler.assemble()
        assembler.finish_assemble()
        # finish_assemble schedules layer composition work on Kit's event loop.
        # NVIDIA's own assembler test allows ten updates; use twelve before
        # resolving mount prims for a subsequent attachment.
        _settle_kit_updates(steps=12)
    except Exception as exc:
        try:
            assembler.cancel_assembly()
            _settle_kit_updates()
        except Exception:
            # Preserve the original assembly error. The process exits on this
            # path, so a failed best-effort session-layer cleanup is harmless.
            pass
        if isinstance(exc, MobileManipulatorAssemblyError):
            raise
        raise MobileManipulatorAssemblyError(
            f"Failed to assemble {attach_robot_path} onto {base_robot_path}: {exc}"
        ) from exc


def _find_named_descendant(stage, root_path: str, name: str):
    expected = _normalise_prim_name(name)
    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        return None
    for prim in _descendants(root):
        if _normalise_prim_name(prim.GetName()) == expected:
            return prim
    return None


def _set_angular_drive_target(stage, joint_prim, target_degrees: float) -> None:
    from pxr import UsdPhysics

    drive = UsdPhysics.DriveAPI.Get(joint_prim, "angular")
    if not drive:
        drive = UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
    target = drive.GetTargetPositionAttr()
    if not target:
        target = drive.CreateTargetPositionAttr()
    target.Set(float(target_degrees))


def _set_safe_pose(
    stage,
    config: MobileManipulatorConfig,
    log: Callable[[str], None],
) -> None:
    missing_arm_joints: list[str] = []
    for joint_name, target in zip(UR10E_JOINT_NAMES, config.ur10e_stow_degrees):
        joint = _find_named_descendant(stage, UR10E_PRIM_PATH, joint_name)
        if joint is None:
            missing_arm_joints.append(joint_name)
            continue
        _set_angular_drive_target(stage, joint, target)

    if missing_arm_joints:
        raise MobileManipulatorAssemblyError(
            "UR10e safe pose could not be applied; missing joints: "
            + ", ".join(missing_arm_joints)
        )

    for joint_name in ROBOTIQ_OPEN_JOINT_CANDIDATES:
        joint = _find_named_descendant(stage, ROBOTIQ_2F140_PRIM_PATH, joint_name)
        if joint is not None:
            _set_angular_drive_target(stage, joint, 0.0)
            log(f"Robotiq 2F-140 held open via {joint.GetPath()}")
            return
    log(
        "Robotiq driving joint was not auto-detected; retaining the asset's "
        "documented default-open pose (no gripper commands are exposed)"
    )


def build_mobile_manipulator(
    stage,
    assets_root_path: str,
    *,
    config: MobileManipulatorConfig | None = None,
    log: Callable[[str], None] = print,
) -> MobileManipulatorAssembly:
    """Load, validate and assemble the OmniGuard mobile manipulator."""

    from isaacsim.core.utils.stage import add_reference_to_stage
    from pxr import UsdGeom

    config = config or MobileManipulatorConfig.from_env()
    existing = stage.GetPrimAtPath(MOBILE_MANIPULATOR_ROOT_PRIM_PATH)
    if existing.IsValid():
        raise MobileManipulatorAssemblyError(
            f"Stage already contains {MOBILE_MANIPULATOR_ROOT_PRIM_PATH}"
        )

    UsdGeom.Xform.Define(stage, MOBILE_MANIPULATOR_ROOT_PRIM_PATH)
    asset_paths = {
        IWHUB_PRIM_PATH: resolve_asset_path(assets_root_path, config.iwhub_usd),
        UR10E_PRIM_PATH: resolve_asset_path(assets_root_path, config.ur10e_usd),
        ROBOTIQ_2F140_PRIM_PATH: resolve_asset_path(
            assets_root_path, config.robotiq_usd
        ),
    }
    for prim_path, usd_path in asset_paths.items():
        log(f"Loading Isaac asset {usd_path} at {prim_path}")
        add_reference_to_stage(usd_path=usd_path, prim_path=prim_path)

    _wait_for_references(
        stage,
        asset_paths,
        timeout_seconds=config.asset_load_timeout_seconds,
    )

    base_arm_mount = _resolve_mount_path(
        stage,
        robot_root_path=IWHUB_PRIM_PATH,
        override=config.iwhub_arm_mount,
        candidates=IWHUB_ARM_MOUNT_CANDIDATES,
        role="iw.hub arm mount",
    )
    arm_base_mount = _resolve_mount_path(
        stage,
        robot_root_path=UR10E_PRIM_PATH,
        override=config.ur10e_base_mount,
        candidates=UR10E_BASE_MOUNT_CANDIDATES,
        role="UR10e base mount",
    )
    arm_tool_mount = _resolve_mount_path(
        stage,
        robot_root_path=UR10E_PRIM_PATH,
        override=config.ur10e_tool_mount,
        candidates=UR10E_TOOL_MOUNT_CANDIDATES,
        role="UR10e tool mount",
    )
    gripper_base_mount = _resolve_mount_path(
        stage,
        robot_root_path=ROBOTIQ_2F140_PRIM_PATH,
        override=config.robotiq_base_mount,
        candidates=ROBOTIQ_BASE_MOUNT_CANDIDATES,
        role="Robotiq 2F-140 base mount",
    )

    # Author safe drive targets while all three referenced robot hierarchies
    # are still independently addressable. RobotAssembler later moves authored
    # attachment specs between layers, but preserves these root-layer targets.
    _set_safe_pose(stage, config, log)

    log(
        "Assembling iw.hub -> UR10e using "
        f"{base_arm_mount} -> {arm_base_mount}"
    )
    _assemble_attachment(
        stage,
        base_robot_path=IWHUB_PRIM_PATH,
        base_mount_path=base_arm_mount,
        attach_robot_path=UR10E_PRIM_PATH,
        attach_mount_path=arm_base_mount,
        namespace="Arm",
        variant_name="omniguard_iwhub_ur10e",
        offset=config.arm_offset,
    )

    log(
        "Assembling UR10e -> Robotiq 2F-140 using "
        f"{arm_tool_mount} -> {gripper_base_mount}"
    )
    # The first assembly merges the arm into the iw.hub robot. The second
    # therefore uses iw.hub as the base robot while mounting on an arm link.
    _assemble_attachment(
        stage,
        base_robot_path=IWHUB_PRIM_PATH,
        base_mount_path=arm_tool_mount,
        attach_robot_path=ROBOTIQ_2F140_PRIM_PATH,
        attach_mount_path=gripper_base_mount,
        namespace="Gripper",
        variant_name="omniguard_ur10e_2f140",
        offset=config.gripper_offset,
    )

    log("OmniGuard mobile manipulator assembled; arm stowed and gripper open")
    return MobileManipulatorAssembly(
        root_prim_path=MOBILE_MANIPULATOR_ROOT_PRIM_PATH,
        base_prim_path=IWHUB_PRIM_PATH,
        arm_prim_path=UR10E_PRIM_PATH,
        gripper_prim_path=ROBOTIQ_2F140_PRIM_PATH,
        base_arm_mount_path=base_arm_mount,
        arm_base_mount_path=arm_base_mount,
        arm_tool_mount_path=arm_tool_mount,
        gripper_base_mount_path=gripper_base_mount,
    )