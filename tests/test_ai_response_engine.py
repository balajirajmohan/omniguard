"""AI response engine — action-window decisions, incidents, recovery."""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.actuation import ActuationResult
from backend.decision_orchestrator import DecisionResult
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

HYBRID_SOURCES = {"behavioral_rule", "hybrid_rule_ml", "action_window_ai"}


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
    if arm["status"] != "REJECTED":
        assert arm.get("decision_source") in {
            None,
            "none",
            "action_window_ai",
            "deterministic_fallback",
            "behavioral_rule",
            "hybrid_rule_ml",
            "ai_warning",
        }


def test_malicious_manipulation_scenario_hybrid_block(monkeypatch):
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
    assert result["decision_source"] in HYBRID_SOURCES
    assert result["caught_by"] in HYBRID_SOURCES
    # Honest contract: ML score alone may be sub-critical; effective / rule drives block.
    assert float(result.get("behavioral_rule_score") or 0) >= 0.80 or float(
        result.get("anomaly_risk_score") or 0
    ) >= 0.80
    assert float(result.get("effective_risk") or 0) >= 0.80
    assert result.get("incident_id")
    assert any(c[0] in {"arm", "grip", "move"} for c in calls)
    rejected_steps = [
        s for s in result["steps"] if s["result"].get("status") == "REJECTED"
    ]
    assert rejected_steps
    assert rejected_steps[0]["result"].get("command_id") in {None, ""}


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
    rejected = [s for s in result["steps"] if s["result"].get("status") == "REJECTED"]
    assert rejected
    assert rejected[0]["result"].get("command_id") is None
    # carry is the late arm step that should be blocked before adapter.
    assert "carry" not in arm_calls


def test_containment_acks_are_truthful(monkeypatch):
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
    containment = result.get("containment") or {}
    acked = set(containment.get("acknowledged") or result.get("actions") or [])
    unverified = set(containment.get("unverified") or result.get("unverified_actions") or [])
    assert "ROBOT_ESTOP_REQUESTED" in acked or "STOP_BASE" in acked
    assert "STOP_ARM" not in acked or "STOP_ARM" in unverified
    assert "SAFE_GRIPPER" not in acked or "SAFE_GRIPPER" in unverified
    # Without manipulator telemetry, arm/gripper must stay unverified.
    assert "STOP_ARM" in unverified
    assert "SAFE_GRIPPER" in unverified


def test_hold_stops_robot_before_lease_inactive(monkeypatch):
    stop_calls = []

    def track_stop(robot_id):
        stop_calls.append(robot_id)
        return ActuationResult(True, "EXECUTED", command_id="hold-stop")

    monkeypatch.setattr("backend.teleop.maybe_actuate_stop", track_stop)
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_move_xy",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="m"),
    )

    cid = _lease()
    moving = client.post(
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
    assert moving["status"] in {"EXECUTED", "QUEUED"}

    hold = DecisionResult(
        final_decision="HOLD",
        policy_decision="AI_HOLD",
        decision_source="ai_warning",
        hard_policy_would_block=False,
        anomaly_risk_score=0.65,
        behavioral_rule_score=0.0,
        effective_risk=0.65,
        requires_incident=True,
        requires_containment=False,
        requires_pause_stop=True,
        requires_human_review=True,
        response_playbook="SUSPICIOUS_SESSION",
        ai_mode="enforce",
    )

    monkeypatch.setattr(
        "backend.ai_response.ai_engine.evaluate_action",
        lambda **_kwargs: (hold, {"incident_id": "inc-hold-test"}),
    )

    blocked = client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 2,
            "robot_id": "robot-01",
            "x": 2.0,
            "y": 0.0,
            "speed": 0.8,
        },
    ).json()
    assert blocked["status"] == "PAUSED_FOR_REVIEW"
    assert blocked["final_decision"] == "HOLD"
    assert blocked.get("robot_stopped") is True
    assert blocked.get("credential_revoked") is False
    assert blocked.get("stop_ack", {}).get("ok") is True
    assert stop_calls == ["robot-01"]

    state = client.get("/api/state").json()
    assert state["robot_speed"] == 0
    assert state["robot_status"] in {"STOPPED", "IDLE", "PAUSED_FOR_REVIEW"}

    again = client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 3,
            "robot_id": "robot-01",
            "x": 3.0,
            "y": 0.0,
            "speed": 0.8,
        },
    ).json()
    assert again["status"] == "REJECTED"

def test_reset_preserves_incidents():
    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    iid = result["incident_id"]
    assert iid
    client.post("/api/reset")
    payload = client.get(f"/api/incidents/{iid}").json()
    assert payload.get("incident_id") == iid
    listed = client.get("/api/incidents").json()
    assert any(i["incident_id"] == iid for i in listed)


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
        decision_source="hybrid_rule_ml",
    )
    again = store.get(iid)
    assert again["event_count"] >= 2
    store2 = IncidentStore(db)
    assert store2.get(iid)["event_count"] >= 2
    blob = db.read_bytes()
    assert b"fleet-agent-valid-token" not in blob


def test_feedback_and_recovery_gates():
    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    iid = result["incident_id"]
    denied = client.post(
        f"/api/incidents/{iid}/feedback", json={"classification": "CONFIRMED_ATTACK"}
    )
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
    assert restored["recovery"]["idp_workflow_complete"] is True
    assert restored["recovery"]["runtime_access_restored"] is False
    state = client.get("/api/state").json()
    assert state.get("credential_status") in {"REVOKED", "ACTIVE"}  # may still be revoked


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
    assert inv["ok"] is True
    assert inv["investigation"]["agent"] == "omniguard-investigation-v2"
    assert inv["investigation"]["execution_authorized"] is False
    assert inv["investigation"]["confidence"] is None
    assert inv["explanation"]["fallback_used"] is True
    # Second call still allowed (max 2); third must be limited.
    inv2 = client.post(f"/api/incidents/{iid}/investigate", headers=OP).json()
    assert inv2["ok"] is True
    limited = client.post(f"/api/incidents/{iid}/investigate", headers=OP).json()
    assert limited["ok"] is False
    assert limited["error"] == "LLM_CALL_LIMIT"


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
