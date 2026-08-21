"""Optional actuation into Srikanth's Isaac HTTP bridge.

Used by the primary backend when OMNIGUARD_ROBOT_BACKEND=isaac.
Keeps the runbook poll queue (fake_robot/isaac_bridge) as the default path.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("omniguard.actuation")

# Simple waypoint map shared with Srikanth's warehouse sketch
ZONE_WAYPOINTS = {
    "SAFE_ZONE_A": (0.0, 0.0),
    "SAFE_ZONE_B": (10.0, 4.0),
    "ZONE_A": (0.0, 0.0),
    "ZONE_B": (10.0, 4.0),
    "RESTRICTED_ZONE": (6.0, 8.0),
    "HUMAN_ZONE": (6.0, 8.0),
}


def maybe_actuate_move(robot_id: str, destination: str, speed: float) -> bool | None:
    """Push move to Isaac bridge when enabled. None = mock/skip."""
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    x, y = ZONE_WAYPOINTS.get(destination, (0.0, 0.0))
    ok = IsaacRobotController().move_to(robot_id, x, y, speed)
    logger.info("Isaac move %s -> %s ok=%s", robot_id, destination, ok)
    return ok


def maybe_actuate_stop(robot_id: str) -> bool | None:
    if os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock").lower() != "isaac":
        return None
    from broker.robot_adapter import IsaacRobotController

    ok = IsaacRobotController().emergency_stop(robot_id)
    logger.warning("Isaac e-stop %s ok=%s", robot_id, ok)
    return ok
