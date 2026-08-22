from __future__ import annotations

import math

import pytest

from backend.zones import TELEOP_ZONES, ZONE_WAYPOINTS
from isaac.demo_geometry import snap_heading_degrees, third_person_camera_eye
from isaac.zone_visuals import (
    ROOT_PATH,
    build_zone_layouts,
    hazard_stripe_polygons,
    label_polygons,
)


def test_zone_visual_layouts_match_authoritative_teleop_zones() -> None:
    layouts = build_zone_layouts(
        TELEOP_ZONES,
        ZONE_WAYPOINTS,
    )

    assert ROOT_PATH == "/World/OmniGuardZones"
    assert [layout.name for layout in layouts] == [
        "SAFE_ZONE_A",
        "SAFE_ZONE_B",
        "RESTRICTED_ZONE",
    ]
    assert layouts[0].label == "SAFE ZONE A"
    assert layouts[0].waypoint == (-1.0, 8.0)
    assert layouts[1].waypoint == (-1.0, 0.0)
    assert layouts[2].waypoint == (5.5, 4.0)
    assert layouts[0].y_max == 12.0
    assert layouts[2].y_max == 12.0
    assert layouts[2].y_min == -4.0
    assert layouts[2].restricted is True
    assert hazard_stripe_polygons(layouts[2])
    assert not hazard_stripe_polygons(layouts[0])
    assert label_polygons(layouts[0])


@pytest.mark.parametrize(
    ("dx", "dy", "expected"),
    [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 90.0),
        (-1.0, 0.0, -180.0),
        (0.0, -1.0, -90.0),
        (5.0, 2.0, 0.0),
        (2.0, 5.0, 90.0),
    ],
)
def test_snap_heading_degrees_uses_cardinal_90_degree_turns(
    dx: float,
    dy: float,
    expected: float,
) -> None:
    assert snap_heading_degrees(dx, dy) == expected


def test_snap_heading_degrees_ignores_zero_vector() -> None:
    assert snap_heading_degrees(0.0, 0.0) is None


def test_third_person_camera_eye_sits_behind_robot_heading() -> None:
    robot = (10.0, 4.0, 0.5)

    assert third_person_camera_eye(robot, 0.0) == pytest.approx((4.0, 4.0, 3.7))
    assert third_person_camera_eye(robot, 90.0) == pytest.approx((10.0, -2.0, 3.7))
    west_eye = third_person_camera_eye(robot, -180.0)
    assert math.isclose(west_eye[0], 16.0, abs_tol=1e-9)
    assert math.isclose(west_eye[1], 4.0, abs_tol=1e-9)