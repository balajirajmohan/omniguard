from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from isaac.command_bridge import CommandBridge


def _request(method: str, url: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["X-OmniGuard-Bridge-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


@pytest.fixture()
def bridge():
    srv = CommandBridge(host="127.0.0.1", port=0, token="test-token")
    srv.require_auth = True
    srv.start()
    time.sleep(0.05)
    yield srv
    srv.stop()
    time.sleep(0.05)


def _base(bridge: CommandBridge) -> str:
    return f"http://127.0.0.1:{bridge.port}"


def test_unauthenticated_move_rejected(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/move",
        {"robot_id": "robot-01", "x": 1, "y": 2, "speed": 0.5},
    )
    assert code == 401
    assert body["error"] == "unauthorized"


def test_invalid_coordinates_rejected(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/move",
        {"robot_id": "robot-01", "x": "nope", "y": 2, "speed": 0.5},
        token="test-token",
    )
    assert code == 400
    assert "x" in body["error"]


def test_nan_and_outofrange_rejected(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/move",
        {"robot_id": "robot-01", "x": float("nan"), "y": 2, "speed": 0.5},
        token="test-token",
    )
    assert code == 400
    code, body = _request(
        "POST",
        f"{_base(bridge)}/move",
        {"robot_id": "robot-01", "x": 1, "y": 2, "speed": 99},
        token="test-token",
    )
    assert code == 400


def test_valid_move_queued_and_ack(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/move",
        {"robot_id": "robot-01", "x": 3.0, "y": 1.0, "speed": 0.8},
        token="test-token",
    )
    assert code == 200
    assert body["status"] == "QUEUED"
    command_id = body["command_id"]
    move = bridge.pop_move("robot-01")
    assert move is not None
    bridge.mark_executed(command_id, motion_state="MOVING")
    code, status = _request(
        "GET",
        f"{_base(bridge)}/commands/{command_id}",
        token="test-token",
    )
    assert code == 200
    assert status["status"] == "EXECUTED"


def test_stop_prioritized(bridge):
    _request(
        "POST",
        f"{_base(bridge)}/move",
        {"robot_id": "robot-01", "x": 3.0, "y": 1.0, "speed": 0.8},
        token="test-token",
    )
    code, body = _request(
        "POST",
        f"{_base(bridge)}/stop",
        {"robot_id": "robot-01"},
        token="test-token",
    )
    assert code == 200
    assert body["status"] == "QUEUED"
    stop = bridge.pop_stop("robot-01")
    assert stop is not None
    bridge.mark_executed(stop["command_id"], motion_state="STOPPED", speed=0.0)
    code, state = _request(
        "GET",
        f"{_base(bridge)}/state",
        token="test-token",
    )
    assert code == 200
    assert state["motion_state"] == "STOPPED"


def test_stop_clears_pending_arm_and_gripper_commands(bridge):
    _request(
        "POST",
        f"{_base(bridge)}/arm/preset",
        {"robot_id": "robot-01", "preset": "reach"},
        token="test-token",
    )
    _request(
        "POST",
        f"{_base(bridge)}/gripper",
        {"robot_id": "robot-01", "action": "close"},
        token="test-token",
    )
    code, body = _request(
        "POST",
        f"{_base(bridge)}/stop",
        {"robot_id": "robot-01"},
        token="test-token",
    )
    assert code == 200
    assert body["status"] == "QUEUED"
    assert bridge.pop_arm_preset("robot-01") is None
    assert bridge.pop_gripper("robot-01") is None


def test_unauthenticated_arm_preset_rejected(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/arm/preset",
        {"robot_id": "robot-01", "preset": "reach"},
    )
    assert code == 401
    assert body["error"] == "unauthorized"


def test_valid_arm_preset_queued_and_ack(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/arm/preset",
        {"robot_id": "robot-01", "preset": "reach"},
        token="test-token",
    )
    assert code == 200
    assert body["status"] == "QUEUED"
    arm = bridge.pop_arm_preset("robot-01")
    assert arm == {"preset": "reach", "command_id": body["command_id"]}
    bridge.mark_executed(body["command_id"], arm={"mode": "preset", "preset": "reach"})
    code, status = _request(
        "GET",
        f"{_base(bridge)}/commands/{body['command_id']}",
        token="test-token",
    )
    assert code == 200
    assert status["status"] == "EXECUTED"


def test_invalid_arm_preset_rejected(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/arm/preset",
        {"robot_id": "robot-01", "preset": "cartwheel"},
        token="test-token",
    )
    assert code == 400
    assert "preset must be one of" in body["error"]


def test_valid_arm_joints_queued(bridge):
    targets = {"panda_joint1": 10.0, "panda_joint2": -35.0}
    code, body = _request(
        "POST",
        f"{_base(bridge)}/arm/joints",
        {"robot_id": "robot-01", "targets_degrees": targets},
        token="test-token",
    )
    assert code == 200
    assert body["status"] == "QUEUED"
    arm = bridge.pop_arm_joints("robot-01")
    assert arm == {"targets_degrees": targets, "command_id": body["command_id"]}


def test_invalid_arm_joints_rejected(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/arm/joints",
        {"robot_id": "robot-01", "targets_degrees": {"panda_joint1": 999.0}},
        token="test-token",
    )
    assert code == 400
    assert "out of range" in body["error"]


def test_valid_gripper_queued(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/gripper",
        {"robot_id": "robot-01", "action": "open"},
        token="test-token",
    )
    assert code == 200
    assert body["status"] == "QUEUED"
    gripper = bridge.pop_gripper("robot-01")
    assert gripper == {"action": "open", "command_id": body["command_id"]}


def test_invalid_gripper_action_rejected(bridge):
    code, body = _request(
        "POST",
        f"{_base(bridge)}/gripper",
        {"robot_id": "robot-01", "action": "crush"},
        token="test-token",
    )
    assert code == 400
    assert "action must be one of" in body["error"]
