"""Authoritative warehouse zone rectangles for teleoperation.

Geometry matches ui-controller (SAFE_ZONE_A/B and RESTRICTED_ZONE).
Boundary rules (tested):
  - Rectangles are inclusive on all edges.
  - RESTRICTED_ZONE is evaluated first and wins on any overlap.
  - Among safe zones, SAFE_ZONE_A is checked before SAFE_ZONE_B
    (shared edge x=5 belongs to SAFE_ZONE_A).
  - Points outside all rectangles are OUT_OF_BOUNDS (treated as restricted).
"""

from __future__ import annotations

from typing import Any

TELEOP_ZONES: dict[str, dict[str, float]] = {
    "SAFE_ZONE_A": {"x_min": -5.0, "x_max": 5.0, "y_min": -5.0, "y_max": 5.0},
    "SAFE_ZONE_B": {"x_min": 5.0, "x_max": 15.0, "y_min": -5.0, "y_max": 5.0},
    "RESTRICTED_ZONE": {"x_min": 2.0, "x_max": 12.0, "y_min": 5.0, "y_max": 12.0},
}

ALLOWED_TELEOP_ZONES = ("SAFE_ZONE_A", "SAFE_ZONE_B")
MAX_TELEOP_SPEED = 1.5


def _in_rect(zone: dict[str, float], x: float, y: float) -> bool:
    return (
        zone["x_min"] <= x <= zone["x_max"]
        and zone["y_min"] <= y <= zone["y_max"]
    )


def classify_point(x: float, y: float) -> str:
    """Return zone name or OUT_OF_BOUNDS. Restricted wins overlaps."""
    if _in_rect(TELEOP_ZONES["RESTRICTED_ZONE"], x, y):
        return "RESTRICTED_ZONE"
    if _in_rect(TELEOP_ZONES["SAFE_ZONE_A"], x, y):
        return "SAFE_ZONE_A"
    if _in_rect(TELEOP_ZONES["SAFE_ZONE_B"], x, y):
        return "SAFE_ZONE_B"
    return "OUT_OF_BOUNDS"


def is_allowed_teleop_point(x: float, y: float) -> tuple[bool, str]:
    zone = classify_point(x, y)
    return zone in ALLOWED_TELEOP_ZONES, zone


def teleop_config_payload(*, robot_id: str = "robot-01") -> dict[str, Any]:
    return {
        "robot_id": robot_id,
        "max_speed": MAX_TELEOP_SPEED,
        "stream_hz": 8,
        "deadman_timeout_ms": 750,
        "lease_ttl_seconds": 30,
        "zones": TELEOP_ZONES,
        "boundary_rules": {
            "inclusive": True,
            "restricted_priority": True,
            "safe_zone_order": list(ALLOWED_TELEOP_ZONES),
            "shared_edge_x5": "SAFE_ZONE_A",
        },
    }
