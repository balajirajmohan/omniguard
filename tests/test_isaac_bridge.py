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
