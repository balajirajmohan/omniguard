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
    assert classify_point(6.0, 8.0) == "RESTRICTED_ZONE"
    assert classify_point(5.0, 0.0) == "SAFE_ZONE_A"
    assert classify_point(5.01, 0.0) == "SAFE_ZONE_B"
    assert classify_point(0.0, 5.1) == "OUT_OF_BOUNDS"
    assert classify_point(2.0, 5.0) == "RESTRICTED_ZONE"


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
    restricted = _start(x=6.0, y=8.0).json()
    assert restricted["final_decision"] == "BLOCK"
    assert "RESTRICTED_DESTINATION" in restricted["reasons"]
    client.post("/api/reset")
    oob = _start(x=16.0, y=0.0).json()
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
            "x": 4.2,
            "y": 2.7,
            "speed": 0.8,
        },
    ).json()
    assert move["status"] in {"QUEUED", "EXECUTED"}
    assert move["command_id"] == "bridge-cmd-1"
    assert move["zone"] == "SAFE_ZONE_A"
    assert calls and calls[0][1:] == (4.2, 2.7, 0.8)


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
            "x": 3.0,
            "y": 2.0,
            "speed": 0.7,
        },
    )
    state = client.get("/api/state").json()
    pos = state["isaac_bridge_state"]["position"]
    assert math.isclose(pos["x"], 3.0)
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
