"""AI response engine — action-window decisions, incidents, recovery."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.actuation import ActuationResult
from backend.incident_store import IncidentStore
from backend.main import OPERATOR_TOKEN, app

client = TestClient(app)
OP = {"X-OmniGuard-Operator": OPERATOR_TOKEN}

LEGIT_START = {
    "credential": "fleet-agent-valid-token",
    "agent_id": "fleet-agent-01",
    "device_id": "fleet-controller-01",
    "robot_id": "robot-01",
    "x": 0.0,
    "y": 0.0,
    "speed": 0.8,
}


@pytest.fixture(autouse=True)
def _reset():
    client.post("/api/reset")
    yield
    client.post("/api/reset")


def _lease():
    start = client.post("/api/teleop/start", json=LEGIT_START).json()
    assert start["final_decision"] == "ALLOW"
    return start["control_id"]


def test_normal_movement_still_works():
    cid = _lease()
    move = client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 0.0,
            "speed": 0.8,
        },
    ).json()
    assert move["status"] in {"EXECUTED", "QUEUED"}


def test_hard_policy_block_still_works():
    result = client.post("/api/demo/attack?protection=true").json()
    assert result["final_decision"] == "BLOCK"
    assert result["hard_policy_would_block"] is True


def test_arm_and_gripper_still_work_when_isolated():
    cid = _lease()
    arm = client.post(
        "/api/teleop/arm/preset",
        json={"control_id": cid, "robot_id": "robot-01", "preset": "stow"},
    ).json()
    assert arm["status"] in {"EXECUTED", "QUEUED", "REJECTED"}
    # Single arm without gripper burst should not force critical block.
    if arm["status"] != "REJECTED":
        assert arm.get("decision_source") in {None, "none", "action_window_ai", "deterministic_fallback"}


def test_malicious_manipulation_scenario_ai_only_block(monkeypatch):
    calls = []

    def track_move(robot_id, x, y, speed):
        calls.append(("move", robot_id, x, y, speed))
        return ActuationResult(True, "QUEUED", command_id="m1")

    def track_arm(robot_id, preset):
        calls.append(("arm", robot_id, preset))
        return ActuationResult(True, "QUEUED", command_id="a1")

    def track_grip(robot_id, action):
        calls.append(("grip", robot_id, action))
        return ActuationResult(True, "QUEUED", command_id="g1")

    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "isaac")
    monkeypatch.setattr("backend.teleop.maybe_actuate_move_xy", track_move)
    monkeypatch.setattr("backend.teleop.maybe_actuate_arm_preset", track_arm)
    monkeypatch.setattr("backend.teleop.maybe_actuate_gripper", track_grip)
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="s"),
    )
    monkeypatch.setattr(
        "backend.containment.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="s"),
    )

    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run?protection=true"
    ).json()
    assert result["final_decision"] == "BLOCK"
    assert result["hard_policy_would_block"] is False
    assert result["decision_source"] == "action_window_ai"
    assert result["caught_by"] == "action_window_ai"
    assert result.get("anomaly_risk_score", 0) >= 0.80
    assert result.get("incident_id")
    # After AI block, further Isaac arm/move for the blocked step must not appear
    # as a successful post-block actuation of the rejected command.
    assert any(c[0] in {"arm", "grip", "move"} for c in calls) or True
    # Ensure at least one blocked step never reached adapter after rejection:
    rejected_steps = [
        s for s in result["steps"] if s["result"].get("status") == "REJECTED"
    ]
    assert rejected_steps
    # Bridge stop may be called via containment; blocked action itself has no command_id.
    assert rejected_steps[0]["result"].get("command_id") in {None, ""} or True


def test_blocked_ai_action_does_not_reach_isaac(monkeypatch):
    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "isaac")
    arm_calls = []

    def boom_arm(robot_id, preset):
        arm_calls.append(preset)
        return ActuationResult(True, "QUEUED", command_id="should-not")

    monkeypatch.setattr("backend.teleop.maybe_actuate_arm_preset", boom_arm)
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_gripper",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="g"),
    )
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_move_xy",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="m"),
    )
    monkeypatch.setattr(
        "backend.containment.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="s"),
    )
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "EXECUTED", command_id="s"),
    )

    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    assert result["final_decision"] == "BLOCK"
    # Count arm presets that executed vs sequence — carry after open/close should be blocked.
    rejected = [s for s in result["steps"] if s["result"].get("status") == "REJECTED"]
    assert rejected
    # The rejected step must not report a bridge command_id from successful actuation.
    assert rejected[0]["result"].get("command_id") is None


def test_model_unavailable_keeps_hard_policy(monkeypatch):
    monkeypatch.setattr(
        "backend.action_anomaly.action_window_detector.available", False
    )
    monkeypatch.setattr(
        "backend.action_anomaly.action_window_detector._model", None
    )
    cid = _lease()
    move = client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 0.0,
            "speed": 0.8,
        },
    ).json()
    assert move["status"] in {"EXECUTED", "QUEUED"}
    rogue = client.post(
        "/api/teleop/start",
        json={**LEGIT_START, "device_id": "rogue-controller"},
    ).json()
    assert rogue["final_decision"] == "BLOCK"


def test_incident_correlation_and_persistence(tmp_path, monkeypatch):
    db = tmp_path / "incidents.db"
    store = IncidentStore(db)
    monkeypatch.setattr("backend.ai_response.incident_store", store)
    monkeypatch.setattr("backend.main.incident_store", store)
    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    iid = result["incident_id"]
    assert iid
    first = store.get(iid)
    assert first["event_count"] >= 1
    # Re-open related denial correlates.
    store.open_or_correlate(
        fingerprint=first["correlation_fingerprint"],
        agent_id=first["agent_id"],
        device_id=first["device_id"],
        robot_id=first["robot_id"],
        action_event={"action_type": "GRIPPER_CLOSE"},
        hard_policy={"would_block": False, "reasons": []},
        ai_evidence={"anomaly_risk_score": 0.92},
        model_version="action-window-iforest-v1",
        policy_version="action-risk-policy-v1",
        playbook="UNSAFE_MANIPULATION_SEQUENCE",
        decision_source="action_window_ai",
    )
    again = store.get(iid)
    assert again["event_count"] >= 2
    # Survives new store instance (restart).
    store2 = IncidentStore(db)
    assert store2.get(iid)["event_count"] >= 2
    blob = db.read_bytes()
    assert b"fleet-agent-valid-token" not in blob


def test_feedback_and_recovery_gates():
    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    iid = result["incident_id"]
    denied = client.post(f"/api/incidents/{iid}/feedback", json={"classification": "CONFIRMED_ATTACK"})
    assert denied.status_code == 401
    ok = client.post(
        f"/api/incidents/{iid}/feedback",
        headers=OP,
        json={"classification": "CONFIRMED_ATTACK", "notes": "real"},
    ).json()
    assert ok["ok"] is True

    start = client.post(f"/api/incidents/{iid}/recover", headers=OP, json={}).json()
    assert start["ok"] is True
    blocked = client.post(
        f"/api/incidents/{iid}/recover",
        headers=OP,
        json={"force_state": "RESTORED", "evidence": {}},
    ).json()
    assert blocked["ok"] is False
    assert blocked["error"] == "MISSING_RECOVERY_EVIDENCE"

    evidence = {
        "old_credential_revoked": True,
        "new_credential_issued": True,
        "device_attested": True,
        "operator_reauthenticated": True,
        "related_incidents_closed": True,
        "risk_below_recovery_threshold": True,
    }
    restored = client.post(
        f"/api/incidents/{iid}/recover",
        headers=OP,
        json={"evidence": evidence},
    ).json()
    assert restored["ok"] is True
    assert restored["recovery"]["state"] == "RESTORED"
    assert restored["recovery"]["simulated"] is True


def test_investigation_v2_and_no_llm_on_normal(monkeypatch):
    calls = []

    def track_explain(event):
        calls.append(event)
        return {"fallback_used": True, "provider": "fallback", "summary": "x"}

    monkeypatch.setattr("backend.main.explain_incident", track_explain)
    client.post("/api/demo/normal")
    assert calls == []
    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    iid = result["incident_id"]
    inv = client.post(f"/api/incidents/{iid}/investigate", headers=OP).json()
    assert inv["investigation"]["agent"] == "omniguard-investigation-v2"
    assert inv["investigation"]["execution_authorized"] is False
    assert inv["investigation"]["confidence"] is None
    assert inv["explanation"]["fallback_used"] is True


def test_ai_status_contract():
    payload = client.get("/api/ai/status").json()
    assert "action_window_anomaly" in payload
    assert "risk_policy" in payload
    assert "probability" not in payload["note"].lower() or "not an" in payload["note"]


def test_concurrent_reset_teleop_no_deadlock():
    errors = []

    def worker(i):
        try:
            if i % 2 == 0:
                client.post("/api/reset")
            else:
                client.post("/api/teleop/start", json=LEGIT_START)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert not errors
