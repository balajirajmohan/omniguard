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


def test_containment_queued_does_not_ack_stop_base(monkeypatch):
    monkeypatch.setattr(
        "backend.containment.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="q"),
    )
    from backend.containment import ContainmentExecutor

    result = ContainmentExecutor().execute(
        playbook="UNSAFE_MANIPULATION_SEQUENCE",
        robot_id="robot-01",
        incident_id="inc-q",
    )
    acked = set(result["acknowledged"])
    unverified = set(result["unverified"])
    failed = set(result["failed"])
    assert "ROBOT_ESTOP_REQUESTED" in acked
    assert "STOP_BASE" not in acked
    assert "STOP_BASE" in unverified
    assert "STOP_ARM" in unverified
    assert "SAFE_GRIPPER" in unverified
    assert "STOP_ARM" not in acked
    assert "SAFE_GRIPPER" not in acked
    assert not failed
    assert result["ok"] is True


def test_containment_failed_marks_estop_failed(monkeypatch):
    monkeypatch.setattr(
        "backend.containment.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(False, "FAILED", command_id=None, detail="boom"),
    )
    from backend.containment import ContainmentExecutor

    result = ContainmentExecutor().execute(
        playbook="UNSAFE_MANIPULATION_SEQUENCE",
        robot_id="robot-01",
    )
    assert result["ok"] is False
    assert "ROBOT_ESTOP_REQUESTED" in result["failed"]
    assert "STOP_BASE" in result["failed"]
    assert "STOP_ARM" in result["unverified"]
    assert "SAFE_GRIPPER" in result["unverified"]


def _hold_decision() -> DecisionResult:
    return DecisionResult(
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


def test_hold_mock_stop_confirmed(monkeypatch):
    """Mock backend (None actuation) confirms via local mock state."""
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_move_xy",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="m"),
    )
    cid = _lease()
    client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 0.0,
            "speed": 0.8,
        },
    )
    hold = _hold_decision()
    monkeypatch.setattr(
        "backend.ai_response.ai_engine.evaluate_action",
        lambda **_kwargs: (hold, {"incident_id": "inc-hold-mock", "ai_evidence": {}}),
    )
    # Do not patch maybe_actuate_stop — mock backend returns None.
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
    assert blocked["stop_requested"] is True
    assert blocked["stop_request_accepted"] is True
    assert blocked["stop_confirmed"] is True
    assert blocked["robot_stopped"] is True
    assert blocked["robot_stopped"] == blocked["stop_confirmed"]
    assert blocked["stop_stage"] == "MOCK_CONFIRMED"
    assert blocked["credential_revoked"] is False
    state = client.get("/api/state").json()
    assert state["credential_status"] == "ACTIVE"
    assert state["agent_status"] == "TRUSTED"
    assert state["robot_speed"] == 0


def test_hold_isaac_executed(monkeypatch):
    stop_calls = []

    def track_stop(robot_id):
        stop_calls.append(robot_id)
        return ActuationResult(True, "EXECUTED", command_id="hold-stop")

    monkeypatch.setattr("backend.teleop.maybe_actuate_stop", track_stop)
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_move_xy",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="m"),
    )
    arm_calls = []
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_arm_preset",
        lambda *_a, **_k: arm_calls.append("arm") or ActuationResult(True, "QUEUED", command_id="a"),
    )

    cid = _lease()
    client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 0.0,
            "speed": 0.8,
        },
    )
    hold = _hold_decision()
    monkeypatch.setattr(
        "backend.ai_response.ai_engine.evaluate_action",
        lambda **_kwargs: (hold, {"incident_id": "inc-hold-exec", "ai_evidence": {}}),
    )
    blocked = client.post(
        "/api/teleop/arm/preset",
        json={"control_id": cid, "robot_id": "robot-01", "preset": "reach"},
    ).json()
    assert blocked["status"] == "PAUSED_FOR_REVIEW"
    assert blocked["stop_stage"] == "EXECUTED"
    assert blocked["stop_requested"] is True
    assert blocked["stop_request_accepted"] is True
    assert blocked["stop_confirmed"] is True
    assert blocked["robot_stopped"] is True
    assert blocked["stop_ack"]["ok"] is True
    assert blocked["stop_ack"]["stage"] == "EXECUTED"
    assert arm_calls == []  # rejected action never reached adapter
    assert stop_calls == ["robot-01"]
    assert client.get("/api/state").json()["credential_status"] == "ACTIVE"


def test_hold_isaac_queued(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="q-stop"),
    )
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_move_xy",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="m"),
    )
    cid = _lease()
    client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 0.0,
            "speed": 0.8,
        },
    )
    speed_before = client.get("/api/state").json()["robot_speed"]
    hold = _hold_decision()
    monkeypatch.setattr(
        "backend.ai_response.ai_engine.evaluate_action",
        lambda **_kwargs: (hold, {"incident_id": "inc-hold-q", "ai_evidence": {}}),
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
    assert blocked["status"] == "PAUSE_STOP_PENDING"
    assert blocked["stop_requested"] is True
    assert blocked["stop_request_accepted"] is True
    assert blocked["stop_confirmed"] is False
    assert blocked["robot_stopped"] is False
    assert blocked["robot_stopped"] == blocked["stop_confirmed"]
    assert blocked["stop_stage"] == "QUEUED"
    state = client.get("/api/state").json()
    assert state["robot_status"] == "STOP_UNCONFIRMED"
    assert state["robot_speed"] == speed_before


def test_hold_isaac_failed_never_fakes_zero_speed(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(False, "FAILED", detail="estop failed"),
    )
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_move_xy",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="m"),
    )
    cid = _lease()
    client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 0.0,
            "speed": 0.8,
        },
    )
    speed_before = client.get("/api/state").json()["robot_speed"]
    assert speed_before > 0
    hold = _hold_decision()
    monkeypatch.setattr(
        "backend.ai_response.ai_engine.evaluate_action",
        lambda **_kwargs: (
            hold,
            {"incident_id": "inc-hold-fail", "ai_evidence": {}},
        ),
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
    assert blocked["status"] == "PAUSE_STOP_FAILED"
    assert blocked["stop_requested"] is True
    assert blocked["stop_request_accepted"] is False
    assert blocked["stop_confirmed"] is False
    assert blocked["robot_stopped"] is False
    assert blocked["stop_stage"] == "FAILED"
    assert blocked["stop_ack"]["ok"] is False
    state = client.get("/api/state").json()
    assert state["robot_status"] == "STOP_UNCONFIRMED"
    assert state["robot_speed"] == speed_before
    assert state["credential_status"] == "ACTIVE"


def test_hold_queued_then_telemetry_confirms(monkeypatch):
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_stop",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="q2"),
    )
    monkeypatch.setattr(
        "backend.teleop.maybe_actuate_move_xy",
        lambda *_a, **_k: ActuationResult(True, "QUEUED", command_id="m"),
    )
    cid = _lease()
    client.post(
        "/api/teleop/move",
        json={
            "control_id": cid,
            "sequence": 1,
            "robot_id": "robot-01",
            "x": 1.0,
            "y": 0.0,
            "speed": 0.8,
        },
    )
    import backend.main as main_mod

    with main_mod._LOCK:
        main_mod.STATE["robot_speed"] = 0.0
        main_mod.STATE["robot_status"] = "STOPPED"
        main_mod.STATE["mock_bridge_state"]["speed"] = 0.0
        main_mod.STATE["mock_bridge_state"]["motion_state"] = "STOPPED"

    hold = _hold_decision()
    monkeypatch.setattr(
        "backend.ai_response.ai_engine.evaluate_action",
        lambda **_kwargs: (hold, {"incident_id": "inc-hold-tel", "ai_evidence": {}}),
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
    assert blocked["stop_request_accepted"] is True
    assert blocked["stop_confirmed"] is True
    assert blocked["robot_stopped"] is True
    assert blocked["stop_stage"] == "QUEUED"


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

    hold = _hold_decision()
    monkeypatch.setattr(
        "backend.ai_response.ai_engine.evaluate_action",
        lambda **_kwargs: (hold, {"incident_id": "inc-hold-test", "ai_evidence": {}}),
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
    assert blocked.get("stop_confirmed") is True
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


def test_demo_run_id_isolates_incidents_across_reset(monkeypatch):
    result1 = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    iid1 = result1["incident_id"]
    assert iid1
    inc1 = client.get(f"/api/incidents/{iid1}").json()
    run1 = inc1["demo_run_id"]
    assert run1

    # Exhaust LLM call budget on first incident.
    monkeypatch.setattr(
        "backend.main.explain_incident",
        lambda _event: {"fallback_used": True, "provider": "fallback", "summary": "x"},
    )
    inv1 = client.post(f"/api/incidents/{iid1}/investigate", headers=OP).json()
    assert inv1["ok"] is True
    inv1b = client.post(f"/api/incidents/{iid1}/investigate", headers=OP).json()
    assert inv1b["ok"] is True
    limited = client.post(f"/api/incidents/{iid1}/investigate", headers=OP).json()
    assert limited["ok"] is False
    assert limited["error"] == "LLM_CALL_LIMIT"

    before_reset = client.get("/api/state").json()["demo_run_id"]
    reset = client.post("/api/reset").json()
    run_after_reset = reset["demo_run_id"]
    assert run_after_reset != before_reset
    assert run_after_reset != run1
    state2 = client.get("/api/state").json()
    assert state2["demo_run_id"] == run_after_reset

    result2 = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run"
    ).json()
    iid2 = result2["incident_id"]
    assert iid2 != iid1
    inc2 = client.get(f"/api/incidents/{iid2}").json()
    run2 = inc2["demo_run_id"]
    assert run2
    assert run2 != run1
    assert run2 != run_after_reset  # scenario run resets again before creating incident

    # Old incident remains queryable; both listed.
    assert client.get(f"/api/incidents/{iid1}").json()["incident_id"] == iid1
    listed = client.get("/api/incidents").json()
    ids = {i["incident_id"] for i in listed}
    assert iid1 in ids and iid2 in ids

    # Second incident has a fresh LLM budget.
    inv2 = client.post(f"/api/incidents/{iid2}/investigate", headers=OP).json()
    assert inv2["ok"] is True
    assert inv2["call_count"] == 1


def test_sqlite_migrates_demo_run_id_without_data_loss(tmp_path):
    import sqlite3

    db = tmp_path / "legacy_incidents.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE incidents (
            incident_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            correlation_fingerprint TEXT,
            first_event_at TEXT,
            last_event_at TEXT,
            event_count INTEGER DEFAULT 1,
            agent_id TEXT,
            device_id TEXT,
            robot_id TEXT,
            action_sequence_json TEXT,
            hard_policy_json TEXT,
            ai_evidence_json TEXT,
            model_version TEXT,
            policy_version TEXT,
            containment_json TEXT,
            agent_trace_json TEXT,
            llm_explanation_json TEXT,
            human_feedback_json TEXT,
            recovery_json TEXT,
            playbook TEXT,
            decision_source TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO incidents (
          incident_id, status, correlation_fingerprint,
          first_event_at, last_event_at, event_count,
          agent_id, device_id, robot_id,
          action_sequence_json, hard_policy_json, ai_evidence_json,
          model_version, policy_version, playbook, decision_source
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "INC-LEGACY001",
            "OPEN",
            "legacy-fp",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            1,
            "fleet-agent-01",
            "fleet-controller-01",
            "robot-01",
            "[]",
            "{}",
            "{}",
            "v1",
            "v1",
            "UNSAFE_MANIPULATION_SEQUENCE",
            "behavioral_rule",
        ),
    )
    conn.commit()
    conn.close()

    store = IncidentStore(db)
    legacy = store.get("INC-LEGACY001")
    assert legacy is not None
    assert legacy["demo_run_id"] is None
    assert legacy["agent_id"] == "fleet-agent-01"

    created = store.open_or_correlate(
        fingerprint="new-fp",
        agent_id="fleet-agent-01",
        device_id="fleet-controller-01",
        robot_id="robot-01",
        action_event={"action_type": "ARM_PRESET"},
        hard_policy={"would_block": False, "reasons": []},
        ai_evidence={"anomaly_risk_score": 0.9},
        model_version="v1",
        policy_version="v1",
        playbook="UNSAFE_MANIPULATION_SEQUENCE",
        decision_source="behavioral_rule",
        demo_run_id="run-migration-1",
    )
    assert created["demo_run_id"] == "run-migration-1"
    assert store.get("INC-LEGACY001")["incident_id"] == "INC-LEGACY001"
    blob = db.read_bytes()
    assert b"fleet-agent-valid-token" not in blob


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
        demo_run_id=first["demo_run_id"],
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
    run_ids = []

    def worker(i):
        try:
            if i % 2 == 0:
                payload = client.post("/api/reset").json()
                run_ids.append(payload.get("demo_run_id"))
            else:
                client.post("/api/teleop/start", json=LEGIT_START)
                run_ids.append(client.get("/api/state").json().get("demo_run_id"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert not errors
    assert all(rid for rid in run_ids)
    # Final state has a single coherent demo_run_id.
    final = client.get("/api/state").json()["demo_run_id"]
    assert final
