"""Teleoperation gateway contract tests."""

from __future__ import annotations

import math
import time

import pytest
from fastapi.testclient import TestClient

from backend.actuation import ActuationResult
from backend.main import app, teleop_manager
from backend.zones import classify_point

client = TestClient(app)

LEGIT = {
    "credential": "fleet-agent-valid-token",
    "agent_id": "fleet-agent-01",
    "device_id": "fleet-controller-01",
    "robot_id": "robot-01",
    "x": 0.0,
    "y": 0.0,
    "speed": 0.8,
}


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("OMNIGUARD_ROBOT_BACKEND", raising=False)
    client.post("/api/reset")
    yield
    client.post("/api/reset")


def _start(**overrides):
    body = {**LEGIT, **overrides}
    return client.post("/api/teleop/start", json=body)


def test_teleop_config_zones_and_boundaries():
    cfg = client.get("/api/teleop/config").json()
    assert cfg["max_speed"] == 1.5
    assert cfg["stream_hz"] == 8
    assert cfg["deadman_timeout_ms"] == 750
    assert "SAFE_ZONE_A" in cfg["zones"]
    assert "RESTRICTED_ZONE" in cfg["zones"]
    assert classify_point(5.5, 4.0) == "RESTRICTED_ZONE"
    assert classify_point(-1.0, 4.0) == "SAFE_ZONE_A"
    assert classify_point(-1.0, 3.99) == "SAFE_ZONE_B"
    assert classify_point(-1.0, 12.1) == "OUT_OF_BOUNDS"
    assert classify_point(2.5, 0.0) == "RESTRICTED_ZONE"


def test_legitimate_start_issues_shadow_lease_even_if_risk_elevated():
    result = _start().json()
    assert result["final_decision"] == "ALLOW"
    assert result["policy_decision"] == "TELEOP_LEASE_ISSUED"
    assert result["control_id"]
    assert result["ai"]["enforcement_mode"] == "SHADOW_TELEOP"
    assert result["ai"]["model"] == "IsolationForest"


def test_rogue_device_blocked_no_lease():
    result = _start(device_id="rogue-controller").json()
    assert result["final_decision"] == "BLOCK"
    assert result["control_id"] is None
    assert "UNKNOWN_DEVICE" in result["reasons"]
    state = client.get("/api/state").json()
    assert state["credential_status"] == "REVOKED"


def test_restricted_and_out_of_bounds_blocked():
    restricted = _start(x=6.0, y=5.0).json()
    assert restricted["final_decision"] == "BLOCK"
    assert "RESTRICTED_DESTINATION" in restricted["reasons"]
    client.post("/api/reset")
    oob = _start(x=13.0, y=0.0).json()
    assert oob["final_decision"] == "BLOCK"
    assert "RESTRICTED_DESTINATION" in oob["reasons"]


def test_overspeed_blocked_on_start():
    result = _start(speed=2.0).json()
    assert result["final_decision"] == "BLOCK"
    assert "EXCESSIVE_SPEED" in result["reasons"]


def test_safe_move_reaches_bridge_adapter(monkeypatch):
    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "isaac")
    calls = []

    def fake_move(robot_id, x, y, speed):
        calls.append((robot_id, x, y, speed))
        return ActuationResult(True, "QUEUED", command_id="bridge-cmd-1")

    monkeypatch.setattr("backend.teleop.maybe_actuate_move_xy", fake_move)
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    start = _start().json()
    assert start["final_decision"] == "ALLOW"
    move = client.post(
        "/api/teleop/move",
        json={
            "control_id": start["control_id"],
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 6.0,
            "speed": 0.8,
        },
    ).json()
    assert move["status"] in {"QUEUED", "EXECUTED"}
    assert move["command_id"] == "bridge-cmd-1"
    assert move["zone"] == "SAFE_ZONE_A"
    assert calls and calls[0][1:] == (1.0, 6.0, 0.8)


def test_bridge_failure_surfaced(monkeypatch):
    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "isaac")

    def boom(*_a, **_k):
        return ActuationResult(False, "FAILED", detail="down")

    monkeypatch.setattr("backend.teleop.maybe_actuate_move_xy", boom)
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    start = _start().json()
    move = client.post(
        "/api/teleop/move",
        json={
            "control_id": start["control_id"],
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 1.0,
            "speed": 0.5,
        },
    ).json()
    assert move["status"] == "FAILED"
    assert "BRIDGE_FAILURE" in move["reasons"]


def test_valid_arm_preset_reaches_actuation(monkeypatch):
    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "isaac")
    calls = []

    def fake_arm(robot_id, preset):
        calls.append((robot_id, preset))
        return ActuationResult(True, "QUEUED", command_id="arm-cmd-1")

    monkeypatch.setattr("backend.teleop.maybe_actuate_arm_preset", fake_arm)
    start = _start().json()
    result = client.post(
        "/api/teleop/arm/preset",
        json={
            "control_id": start["control_id"],
            "robot_id": "robot-01",
            "preset": "reach",
        },
    ).json()
    assert result["status"] == "QUEUED"
    assert result["command_id"] == "arm-cmd-1"
    assert result["preset"] == "reach"
    assert calls == [("robot-01", "reach")]


def test_valid_gripper_reaches_actuation(monkeypatch):
    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "isaac")
    calls = []

    def fake_gripper(robot_id, action):
        calls.append((robot_id, action))
        return ActuationResult(True, "QUEUED", command_id="grip-cmd-1")

    monkeypatch.setattr("backend.teleop.maybe_actuate_gripper", fake_gripper)
    start = _start().json()
    result = client.post(
        "/api/teleop/gripper",
        json={
            "control_id": start["control_id"],
            "robot_id": "robot-01",
            "action": "close",
        },
    ).json()
    assert result["status"] == "QUEUED"
    assert result["command_id"] == "grip-cmd-1"
    assert result["action"] == "close"
    assert calls == [("robot-01", "close")]


def test_arm_preset_unknown_lease_rejected(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_arm_preset",
        lambda *args: calls.append(args) or ActuationResult(True, "QUEUED"),
    )
    result = client.post(
        "/api/teleop/arm/preset",
        json={
            "control_id": "not-a-real-lease",
            "robot_id": "robot-01",
            "preset": "reach",
        },
    ).json()
    assert result["status"] == "REJECTED"
    assert "UNKNOWN_OR_MISMATCHED_LEASE" in result["reasons"]
    assert calls == []


def test_gripper_revoked_credential_rejected(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    calls = []
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_gripper",
        lambda *args: calls.append(args) or ActuationResult(True, "QUEUED"),
    )
    start = _start().json()
    client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "rogue-controller",
            "destination": "RESTRICTED_ZONE",
            "speed": 3.5,
        },
    )
    result = client.post(
        "/api/teleop/gripper",
        json={
            "control_id": start["control_id"],
            "robot_id": "robot-01",
            "action": "close",
        },
    ).json()
    assert result["status"] == "REJECTED"
    assert "REVOKED_CREDENTIAL" in result["reasons"]
    assert calls == []


def test_replayed_sequence_rejected(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    start = _start().json()
    cid = start["control_id"]
    body = {
        "control_id": cid,
        "sequence": 1,
        "robot_id": "robot-01",
        "x": 1.0,
        "y": 1.0,
        "speed": 0.5,
    }
    assert client.post("/api/teleop/move", json=body).json()["status"] in {
        "EXECUTED",
        "QUEUED",
    }
    again = client.post("/api/teleop/move", json=body).json()
    assert again["status"] == "REJECTED"
    assert "SEQUENCE_REPLAY" in again["reasons"]


def test_expired_lease_rejected(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    start = _start().json()
    cid = start["control_id"]
    assert cid
    from datetime import datetime, timedelta, timezone

    with teleop_manager._lock:
        lease = teleop_manager._by_id[cid]
        lease.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    move = client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 1.0,
            "speed": 0.5,
        },
    ).json()
    assert move["status"] == "REJECTED"
    assert "LEASE_EXPIRED" in move["reasons"]


def test_deadman_expiry_sends_stop(monkeypatch):
    monkeypatch.setattr("backend.teleop.DEADMAN_TIMEOUT_MS", 40)
    stops = []

    def fake_stop(robot_id):
        stops.append(robot_id)
        return ActuationResult(True, "EXECUTED", command_id="stop-1")

    monkeypatch.setattr("backend.teleop.maybe_actuate_stop", fake_stop)
    start = _start().json()
    assert start["control_id"]
    client.post(
        "/api/teleop/move",
        json={
            "control_id": start["control_id"],
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 1.0,
            "speed": 0.5,
        },
    )
    deadline = time.time() + 2.0
    found = False
    while time.time() < deadline:
        events = client.get("/api/events").json()
        found = any(
            e.get("kind") == "teleop_deadman"
            or "TELEOP_DEADMAN_STOP" in (e.get("reasons") or [])
            or "TELEOP_DEADMAN_STOP" in (e.get("actions") or [])
            for e in events
        )
        if found:
            break
        time.sleep(0.05)
    assert found
    assert stops


def test_revoked_credential_cannot_continue_lease(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    start = _start().json()
    cid = start["control_id"]
    client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "rogue-controller",
            "destination": "RESTRICTED_ZONE",
            "speed": 3.5,
        },
    )
    move = client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 1.0,
            "speed": 0.5,
        },
    ).json()
    assert move["status"] == "REJECTED"
    assert "REVOKED_CREDENTIAL" in move["reasons"]


def test_only_one_active_lease_per_robot(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    first = _start().json()
    second = _start(x=1.0, y=1.0).json()
    assert first["control_id"] and second["control_id"]
    assert first["control_id"] != second["control_id"]
    old = client.post(
        "/api/teleop/move",
        json={
            "control_id": first["control_id"],
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 1.0,
            "speed": 0.5,
        },
    ).json()
    assert old["status"] == "REJECTED"
    ok = client.post(
        "/api/teleop/move",
        json={
            "control_id": second["control_id"],
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 1.0,
            "speed": 0.5,
        },
    ).json()
    assert ok["status"] in {"EXECUTED", "QUEUED"}


def test_no_public_endpoint_returns_bridge_token(monkeypatch):
    monkeypatch.setenv("ISAAC_BRIDGE_TOKEN", "super-secret-bridge-token")
    for path in ("/health", "/api/state", "/api/teleop/config"):
        blob = str(client.get(path).json())
        assert "super-secret-bridge-token" not in blob
        assert "ISAAC_BRIDGE_TOKEN" not in blob


def test_state_exposes_physical_position():
    start = _start().json()
    assert start["control_id"]
    client.post(
        "/api/teleop/move",
        json={
            "control_id": start["control_id"],
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 2.0,
            "speed": 0.7,
        },
    )
    state = client.get("/api/state").json()
    pos = state["isaac_bridge_state"]["position"]
    assert math.isclose(pos["x"], 1.0)
    assert math.isclose(pos["y"], 2.0)


def test_non_finite_coordinates_blocked():
    from backend.main import teleop_manager as mgr

    result = mgr.start({**LEGIT, "x": float("nan")})
    assert result["final_decision"] == "BLOCK"
    assert result["control_id"] is None


def test_stop_accepts_known_lease(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="stop"),
    )
    start = _start().json()
    stop = client.post(
        "/api/teleop/stop",
        json={
            "control_id": start["control_id"],
            "robot_id": "robot-01",
            "reason": "JOYSTICK_RELEASED",
        },
    ).json()
    assert stop["status"] in {"EXECUTED", "QUEUED", "FAILED"}


def test_no_blocking_calls_under_teleop_lock():
    """The deadman needs TeleopManager._lock every 100 ms.

    Bridge HTTP and the API-state callbacks must therefore never run while it is
    held: the callbacks re-enter _LOCK (which reset_state holds while calling
    into the manager), and the bridge calls block for seconds when Isaac is
    slow, which would stall the 750 ms deadman that stops a runaway robot.
    """
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "backend" / "teleop.py").read_text()
    lines = source.splitlines()
    forbidden = (
        "maybe_actuate",
        "_append_event(",
        "_apply_containment(",
        "_get_security_state(",
        "_update_mock_pose(",
        "_reject_move(",
        "_reject_aux_command(",
    )

    offenders = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)with self\._lock:", lines[index])
        if not match:
            index += 1
            continue
        indent = len(match.group(1))
        cursor = index + 1
        while cursor < len(lines):
            line = lines[cursor]
            if line.strip() and (len(line) - len(line.lstrip())) <= indent:
                break
            if not line.strip().startswith("#"):
                for name in forbidden:
                    if name in line:
                        offenders.append(f"teleop.py:{cursor + 1}: {line.strip()}")
            cursor += 1
        index = cursor

    assert offenders == [], "blocking or re-entrant calls under TeleopManager._lock:\n" + "\n".join(
        offenders
    )


def test_mock_mode_reports_arm_and_gripper_state(monkeypatch):
    """Mock mode must report arm/gripper in the same shape the Isaac bridge does.

    Without this /api/state can never show manipulator state unless a real
    simulator is attached, so any UI reading isaac_bridge_state stays blank.
    """
    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "mock")
    client.post("/api/reset")

    started = client.post("/api/teleop/start", json=LEGIT).json()
    control_id = started["control_id"]
    assert control_id, started

    assert (
        client.post(
            "/api/teleop/arm/preset",
            json={"control_id": control_id, "robot_id": "robot-01", "preset": "carry"},
        ).json()["status"]
        == "EXECUTED"
    )
    assert (
        client.post(
            "/api/teleop/gripper",
            json={"control_id": control_id, "robot_id": "robot-01", "action": "open"},
        ).json()["status"]
        == "EXECUTED"
    )

    bridge = client.get("/api/state").json()["isaac_bridge_state"]
    assert bridge["arm"] == {"mode": "preset", "preset": "carry"}
    assert bridge["gripper"]["action"] == "open"
