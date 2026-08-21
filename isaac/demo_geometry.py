"""Renderer-neutral geometry helpers for the Isaac warehouse demo."""

from __future__ import annotations

import math


SNAP_YAW_INCREMENT_DEGREES = 90.0


def normalise_degrees(degrees: float) -> float:
    """Normalise an angle to the [-180, 180) range."""

    return ((degrees + 180.0) % 360.0) - 180.0


def snap_heading_degrees(dx: float, dy: float, *, increment: float = SNAP_YAW_INCREMENT_DEGREES) -> float | None:
    """Return the nearest snapped yaw for a movement vector.

    Isaac's demo movement is intentionally kinematic.  For visual clarity we snap
    the robot to a cardinal heading instead of animating a smooth turn:

    * +X/east/right  -> 0 degrees
    * +Y/north/up    -> 90 degrees
    * -X/west/left   -> -180 degrees
    * -Y/south/down  -> -90 degrees
    """

    if math.isclose(dx, 0.0, abs_tol=1e-9) and math.isclose(dy, 0.0, abs_tol=1e-9):
        return None
    raw = math.degrees(math.atan2(dy, dx))
    snapped = round(raw / increment) * increment
    return normalise_degrees(snapped)


def heading_forward_vector(yaw_degrees: float) -> tuple[float, float]:
    """Return the unit XY vector for a snapped robot heading."""

    radians = math.radians(yaw_degrees)
    return math.cos(radians), math.sin(radians)


def third_person_camera_eye(
    robot_position: tuple[float, float, float],
    yaw_degrees: float,
    *,
    distance: float = 6.0,
    height: float = 3.2,
) -> tuple[float, float, float]:
    """Place the camera behind and above the robot for a third-person view."""

    forward_x, forward_y = heading_forward_vector(yaw_degrees)
    return (
        robot_position[0] - forward_x * distance,
        robot_position[1] - forward_y * distance,
        robot_position[2] + height,
    )