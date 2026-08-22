"""Unified incidents + async Sonnet investigation."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.incident_classification import classify_security_record
from backend.incident_service import note_audit_event
from backend.main import OPERATOR_TOKEN, VALID_TOKEN, app, reset_state
from backend.policy import KNOWN_DEVICE

client = TestClient(app)
OP = {"X-OmniGuard-Operator": OPERATOR_TOKEN}


@pytest.fixture(autouse=True)
def _reset():
    client.post("/api/reset")
    yield
    client.post("/api/reset")


def test_classify_audit_vs_incident():
    assert (
        classify_security_record(
            {"kind": "teleop_stop", "reasons": ["JOYSTICK_RELEASED"]}
        )
        == "AUDIT_EVENT"
    )
    assert (
        classify_security_record(
            {
                "final_decision": "BLOCK",
                "reasons": ["UNKNOWN_DEVICE"],
            }
        )
        == "INCIDENT"
    )
    assert (
        classify_security_record(
            {
                "final_decision": "HOLD",
                "decision_source": "ai_warning",
                "requires_human_review": True,
            }
        )
        == "INCIDENT"
    )


def test_hard_policy_blocks_create_durable_incidents():
    cases = [
        ({"device_id": "rogue-pad"}, "UNKNOWN_DEVICE", "hard_policy"),
        (
            {"destination": "RESTRICTED_ZONE"},
            "RESTRICTED_DESTINATION",
            "hard_policy",
        ),
        ({"speed": 9.0}, "EXCESSIVE_SPEED", "hard_policy"),
    ]
    for extra, reason, source in cases:
        client.post("/api/reset")
        body = {
            "credential": VALID_TOKEN,
            "agent_id": "fleet-agent-01",
            "device_id": KNOWN_DEVICE,
            "robot_id": "robot-01",
            "destination": "SAFE_ZONE_B",
            "speed": 0.8,
            **extra,
        }
        result = client.post("/api/commands", json=body).json()
        assert result["final_decision"] == "BLOCK"
        assert reason in result["reasons"]
        assert result.get("incident_id")
        assert result.get("investigation_status") == "PENDING"
        assert result.get("decision_source") == source
        assert (result.get("containment") or {}).get("ok") is True
        stored = client.get(f"/api/incidents/{result['incident_id']}").json()
        assert stored["decision_source"] == "hard_policy"
        assert stored["playbook"]


def test_block_returns_before_slow_llm(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def slow_explain(event):
        calls["n"] += 1
        started.set()
        release.wait(timeout=30)
        return {
            "summary": "delayed",
            "fallback_used": True,
            "provider": "fallback",
            "status": "COMPLETED",
        }

    monkeypatch.setattr("backend.incident_ai.explain_incident", slow_explain)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    t0 = time.perf_counter()
    result = client.post(
        "/api/commands",
        json={
            "credential": VALID_TOKEN,
            "agent_id": "fleet-agent-01",
            "device_id": "evil-device",
            "robot_id": "robot-01",
            "destination": "SAFE_ZONE_A",
            "speed": 0.8,
        },
    ).json()
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0
    assert result["final_decision"] == "BLOCK"
    assert result["incident_id"]
    assert result["investigation_status"] == "PENDING"
    assert (result.get("containment") or {}).get("ok") is True

    # API stays responsive while LLM sleeps.
    assert client.get("/health").json()["status"] == "ok"
    assert "robot_status" in client.get("/api/state").json()
    safe = client.post(
        "/api/commands",
        json={
            "credential": VALID_TOKEN,
            "agent_id": "fleet-agent-01",
            "device_id": KNOWN_DEVICE,
            "robot_id": "robot-01",
            "destination": "SAFE_ZONE_B",
            "speed": 0.8,
        },
    )
    # May be BLOCK due to revoked credential from prior containment — still fast.
    assert safe.status_code == 200
    assert time.perf_counter() - t0 < 3.0

    release.set()
    iid = result["incident_id"]
    for _ in range(80):
        inc = client.get(f"/api/incidents/{iid}").json()
        status = (inc.get("llm_explanation") or {}).get("status")
        if status in {"COMPLETED", "FAILED"}:
            break
        time.sleep(0.05)
    else:
        pytest.fail("investigation did not complete")
    assert calls["n"] >= 1


def test_llm_failure_does_not_take_api_down(monkeypatch):
    def boom(_event):
        raise RuntimeError("provider down")

    monkeypatch.setattr("backend.incident_ai.explain_incident", boom)
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    result = client.post("/api/demo/attack?protection=true").json()
    assert result["final_decision"] == "BLOCK"
    assert result.get("incident_id")
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/state").status_code == 200


def test_joystick_release_no_incident():
    before = {i["incident_id"] for i in client.get("/api/incidents").json()}
    start = client.post(
        "/api/teleop/start",
        json={
            "credential": VALID_TOKEN,
            "agent_id": "fleet-agent-01",
            "device_id": KNOWN_DEVICE,
            "robot_id": "robot-01",
            "x": 0.0,
            "y": 0.0,
            "speed": 0.8,
        },
    ).json()
    assert start["final_decision"] == "ALLOW"
    cid = start["control_id"]
    client.post(
        "/api/teleop/stop",
        json={"control_id": cid, "robot_id": "robot-01", "reason": "JOYSTICK_RELEASED"},
    )
    after = {i["incident_id"] for i in client.get("/api/incidents").json()}
    assert after == before


def test_audit_threshold_escalates_once(monkeypatch):
    client.post("/api/reset")
    state = client.get("/api/state").json()
    run = state["demo_run_id"]
    last = None
    for _ in range(5):
        last = note_audit_event(
            reason="SEQUENCE_REPLAY",
            agent_id="fleet-agent-01",
            device_id=KNOWN_DEVICE,
            robot_id="robot-01",
            session_id="sess-1",
            demo_run_id=run,
        )
    assert last is not None
    iid = last.get("incident_id")
    assert iid
    stored = client.get(f"/api/incidents/{iid}").json()
    assert stored["incident_id"] == iid
    assert "CONTROL_PROTOCOL" in str(stored.get("hard_policy") or {}) or stored.get(
        "playbook"
    )


def test_manipulation_scenario_still_blocks():
    result = client.post(
        "/api/scenarios/valid_identity_malicious_manipulation/run?protection=true"
    ).json()
    assert result["final_decision"] == "BLOCK"
    assert result.get("incident_id")
    assert result.get("hard_policy_would_block") is False
