from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.actuation import ActuationResult
from backend.main import SIMULATOR_TOKEN, app
from backend.scenarios import SCENARIOS

client = TestClient(app)
SIM_HEADERS = {"X-OmniGuard-Simulator": SIMULATOR_TOKEN}

EXPECTED_DECISIONS = {
    "normal": {"ALLOW"},
    "rogue_device": {"BLOCK"},
    "geofence": {"BLOCK"},
    "excessive_speed": {"BLOCK"},
    "command_burst": {"HOLD"},
    "combined_attack": {"BLOCK"},
    "behavioral_anomaly": {"BLOCK"},
    "revoked_replay": {"BLOCK"},
    "valid_identity_malicious_manipulation": {"BLOCK"},
}


@pytest.fixture(autouse=True)
def _reset():
    client.post("/api/reset")
    yield
    client.post("/api/reset")


def test_health_contract():
    payload = client.get("/health").json()
    assert payload["status"] == "ok"
    assert "ai_enforcement_enabled" in payload
    assert "model_available" in payload
    assert "artifact_verified" in payload
    assert payload["llm"]["controls_robot"] is False
    assert payload["anomaly"]["controls_robot"] is False


def test_every_scenario_decision_and_signals():
    for scenario in SCENARIOS:
        result = client.post(
            f"/api/scenarios/{scenario['id']}/run?protection=true&reset_first=true"
        ).json()
        assert result["final_decision"] in EXPECTED_DECISIONS[scenario["id"]], scenario["id"]
        for signal in scenario.get("expected_signals") or []:
            assert signal in result["reasons"], (scenario["id"], signal, result["reasons"])


def test_ai_only_containment():
    result = client.post("/api/demo/anomaly").json()
    assert result["final_decision"] == "BLOCK"
    assert result["hard_policy_would_block"] is False
    assert result["caught_by"] == "ai_anomaly"
    assert result["anomaly_risk_score"] >= 0.80
    assert "AI_ANOMALY_CONTAINMENT" in result["actions"]


def test_command_burst_is_ai_warning_or_block():
    result = client.post(
        "/api/scenarios/command_burst/run?protection=true&reset_first=true"
    ).json()
    assert result["final_decision"] == "HOLD"
    assert result["caught_by"] == "ai_warning"
    assert "AI_WARNING" in result["actions"]
    assert 0.60 <= result["anomaly_risk_score"] < 0.80


def test_ai_shadow_mode(monkeypatch):
    monkeypatch.setenv("OMNIGUARD_AI_ENFORCE", "false")
    # Re-import policy flag used by decide — patch module attribute.
    import backend.policy as policy
    import backend.main as main

    monkeypatch.setattr(policy, "AI_ENFORCE", False)
    monkeypatch.setattr(main, "AI_ENFORCE", False)
    result = client.post("/api/demo/anomaly").json()
    assert result["final_decision"] == "ALLOW"
    assert result["policy_decision"] == "AI_SHADOW_ALERT"
    assert result["caught_by"] == "ai_shadow"


def test_caller_cannot_inject_behavioral_features():
    rejected = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "fleet-controller-01",
            "destination": "SAFE_ZONE_B",
            "speed": 1.45,
            "commands_last_10_seconds": 1,
            "previous_failures": 0,
            "hour_of_day": 10,
            "seconds_since_last_command": 60,
        },
    )
    assert rejected.status_code == 422


def test_server_derived_behavior_history():
    first = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "fleet-controller-01",
            "destination": "SAFE_ZONE_B",
            "speed": 0.8,
        },
    ).json()
    assert first["behavior"]["source"] == "server"
    second = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "fleet-controller-01",
            "destination": "SAFE_ZONE_B",
            "speed": 0.8,
        },
    ).json()
    assert second["behavior"]["commands_last_10_seconds"] >= 1


def test_normal_is_allowed():
    result = client.post("/api/demo/normal").json()
    assert result["final_decision"] == "ALLOW"
    assert result["policy_decision"] == "PERMIT"


def test_attack_is_blocked():
    result = client.post("/api/demo/attack?protection=true").json()
    assert result["final_decision"] == "BLOCK"
    assert "CREDENTIAL_REVOKED" in result["actions"]
    state = client.get("/api/state").json()
    assert state["credential_status"] == "REVOKED"
    assert state["robot_speed"] == 0.0


def test_unprotected_attack_is_forwarded():
    result = client.post(
        "/api/demo/attack?protection=false",
        headers={"X-OmniGuard-Operator": "omniguard-operator"},
    ).json()
    assert result["final_decision"] == "ALLOW"
    assert result["policy_decision"] == "BYPASSED"


def test_unprotected_attack_requires_operator():
    denied = client.post("/api/demo/attack?protection=false")
    assert denied.status_code == 401


def test_commands_cannot_disable_protection():
    # Extra field rejected; body without protection always enforces.
    rejected = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "unknown-attacker-device",
            "destination": "RESTRICTED_ZONE",
            "speed": 3.5,
            "protection_enabled": False,
        },
    )
    assert rejected.status_code == 422
    blocked = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "unknown-attacker-device",
            "destination": "RESTRICTED_ZONE",
            "speed": 3.5,
        },
    ).json()
    assert blocked["final_decision"] == "BLOCK"
    assert blocked["protection_enabled"] is True


def test_revoked_credential_stays_blocked():
    client.post("/api/demo/attack?protection=true")
    again = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "fleet-controller-01",
            "destination": "SAFE_ZONE_B",
            "speed": 0.8,
        },
    ).json()
    assert again["final_decision"] == "BLOCK"
    assert "REVOKED_CREDENTIAL" in again["reasons"]


def test_unknown_zone_is_blocked():
    result = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "fleet-controller-01",
            "destination": "UNSAFE_ZONE",
            "speed": 0.8,
        },
    ).json()
    assert result["final_decision"] == "BLOCK"
    assert "RESTRICTED_DESTINATION" in result["reasons"]


def test_simulator_channel_requires_auth():
    assert client.get("/api/robots/robot-01/next-command").status_code == 401


def test_fake_robot_contract():
    client.post("/api/demo/normal")
    cmd = client.get("/api/robots/robot-01/next-command", headers=SIM_HEADERS).json()
    while cmd.get("action") == "RESET":
        cmd = client.get("/api/robots/robot-01/next-command", headers=SIM_HEADERS).json()
    assert cmd["action"] == "MOVE"
    ack = client.post(
        "/api/robots/robot-01/telemetry",
        headers=SIM_HEADERS,
        json={"status": "ARRIVED", "zone": "SAFE_ZONE_B", "speed": 0.0},
    )
    assert ack.status_code == 200


def test_telemetry_cannot_override_containment():
    client.post("/api/demo/attack?protection=true")
    denied = client.post(
        "/api/robots/robot-01/telemetry",
        headers=SIM_HEADERS,
        json={"status": "ARRIVED", "zone": "RESTRICTED_ZONE", "speed": 3.5},
    )
    assert denied.status_code == 409


def test_failed_isaac_estop_surfaces(monkeypatch):
    monkeypatch.setenv("OMNIGUARD_ROBOT_BACKEND", "isaac")

    def boom(*_a, **_k):
        return ActuationResult(False, "FAILED", detail="bridge down")

    monkeypatch.setattr("backend.main.maybe_actuate_stop", boom)
    result = client.post("/api/demo/attack?protection=true").json()
    assert "ISAAC_ESTOP_FAILED" in result["actions"]
    assert client.get("/api/state").json()["robot_status"] == "CONTAINMENT_FAILED"


def test_investigation_agent_cannot_move_robots():
    client.post("/api/demo/attack?protection=true")
    result = client.post("/api/investigate").json()
    assert "arbitrary_robot_movement" in result["disallowed"]
    assert set(result["tools_used"]) >= {
        "get_recent_events",
        "recommend_containment",
        "create_incident_report",
    }


def test_dashboard_api_smoke_contract():
    assert client.get("/api/scenarios").status_code == 200
    assert client.get("/api/events").status_code == 200
    assert client.get("/api/timeline").status_code == 200
    assert client.get("/api/incidents/latest").status_code == 200
