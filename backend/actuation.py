"""Optional actuation into the Isaac HTTP bridge with command acknowledgement."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("omniguard.actuation")

ZONE_WAYPOINTS = {
    "SAFE_ZONE_A": (0.0, 0.0),
    "SAFE_ZONE_B": (10.0, 4.0),
    "ZONE_A": (0.0, 0.0),
    "ZONE_B": (10.0, 4.0),
    "RESTRICTED_ZONE": (6.0, 8.0),
    "HUMAN_ZONE": (6.0, 8.0),
}


@dataclass
class ActuationResult:
    ok: bool
    stage: str  # QUEUED | EXECUTED | FAILED | SKIPPED
    command_id: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stage": self.stage,
            "command_id": self.command_id,
            "detail": self.detail,
        }


def _poll_command(controller, command_id: str, timeout: float = 2.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = controller.get_command_status(command_id)
        if status in {"EXECUTED", "FAILED"}:
            return status
        time.sleep(0.05)
    return "QUEUED"


def maybe_actuate_move_xy(
    robot_id: str, x: float, y: float, speed: float
) -> ActuationResult | None:
    """Push an absolute XY target to the Isaac bridge when enabled."""
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    controller = IsaacRobotController()
    queued = controller.move_to_queued(robot_id, x, y, speed)
    if not queued.get("ok"):
        return ActuationResult(False, "FAILED", detail=queued.get("error"))
    command_id = queued.get("command_id")
    # Teleop is latency-sensitive: return QUEUED quickly; reconcile via /api/state.
    return ActuationResult(True, "QUEUED", command_id=command_id)


def maybe_actuate_move(robot_id: str, destination: str, speed: float) -> ActuationResult | None:
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    x, y = ZONE_WAYPOINTS.get(destination, (0.0, 0.0))
    controller = IsaacRobotController()
    queued = controller.move_to_queued(robot_id, x, y, speed)
    if not queued.get("ok"):
        return ActuationResult(False, "FAILED", detail=queued.get("error"))
    command_id = queued.get("command_id")
    stage = _poll_command(controller, command_id) if command_id else "QUEUED"
    ok = stage in {"QUEUED", "EXECUTED"}
    return ActuationResult(ok, stage, command_id=command_id)


def maybe_actuate_stop(robot_id: str) -> ActuationResult | None:
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    controller = IsaacRobotController()
    queued = controller.emergency_stop_queued(robot_id)
    if not queued.get("ok"):
        return ActuationResult(False, "FAILED", detail=queued.get("error"))
    command_id = queued.get("command_id")
    stage = _poll_command(controller, command_id) if command_id else "QUEUED"
    ok = stage in {"QUEUED", "EXECUTED"}
    return ActuationResult(ok, stage, command_id=command_id)


def maybe_actuate_arm_preset(robot_id: str, preset: str) -> ActuationResult | None:
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    queued = IsaacRobotController().arm_preset_queued(robot_id, preset)
    if not queued.get("ok"):
        return ActuationResult(False, "FAILED", detail=queued.get("error"))
    return ActuationResult(True, "QUEUED", command_id=queued.get("command_id"))


def maybe_actuate_arm_joints(
    robot_id: str, targets_degrees: dict[str, float]
) -> ActuationResult | None:
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    queued = IsaacRobotController().arm_joints_queued(robot_id, targets_degrees)
    if not queued.get("ok"):
        return ActuationResult(False, "FAILED", detail=queued.get("error"))
    return ActuationResult(True, "QUEUED", command_id=queued.get("command_id"))


def maybe_actuate_gripper(robot_id: str, action: str) -> ActuationResult | None:
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    queued = IsaacRobotController().gripper_queued(robot_id, action)
    if not queued.get("ok"):
        return ActuationResult(False, "FAILED", detail=queued.get("error"))
    return ActuationResult(True, "QUEUED", command_id=queued.get("command_id"))


def fetch_bridge_state() -> dict[str, Any] | None:
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    return IsaacRobotController().get_state()
