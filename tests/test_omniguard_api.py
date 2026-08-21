from fastapi.testclient import TestClient

from backend.main import SIMULATOR_TOKEN, app

client = TestClient(app)
SIM_HEADERS = {"X-OmniGuard-Simulator": SIMULATOR_TOKEN}


def test_ai_only_anomaly_blocks_when_rules_pass():
    """Valid identity/device/zone/speed — IsolationForest must catch it."""
    client.post("/api/reset")
    result = client.post("/api/demo/anomaly").json()
    assert result["final_decision"] == "BLOCK"
    assert result["hard_policy_would_block"] is False
    assert result["caught_by"] == "ai_anomaly"
    assert result["policy_decision"] == "REVIEW_AI_RISK"
    assert result["anomaly_risk_score"] >= 0.80
    assert "AI_ANOMALY_CONTAINMENT" in result["actions"]
    assert result.get("anomaly_model_version")


def test_health():
    payload = client.get("/health").json()
    assert payload["status"] == "ok"
    assert "llm" in payload
    assert payload["llm"]["controls_robot"] is False
    assert "anomaly" in payload
    assert payload["anomaly"]["controls_robot"] is False
    assert payload["anomaly"]["model_name"] == "IsolationForest"


def test_scenario_catalog_and_combined_attack():
    catalog = client.get("/api/scenarios").json()
    ids = {item["id"] for item in catalog}
    assert "combined_attack" in ids
    assert "normal" in ids
    blocked = client.post(
        "/api/scenarios/combined_attack/run?protection=true&reset_first=true"
    ).json()
    assert blocked["final_decision"] == "BLOCK"
    assert "UNKNOWN_DEVICE" in blocked["reasons"]
    explanation = blocked.get("incident_explanation") or {}
    assert explanation.get("provider")
    assert "fallback_used" in explanation


def test_normal_is_allowed():
    result = client.post("/api/demo/normal").json()
    assert result["final_decision"] == "ALLOW"
    assert result["policy_decision"] == "PERMIT"
    state = client.get("/api/state").json()
    assert state["robot_status"] == "MOVING"


def test_attack_is_blocked():
    result = client.post("/api/demo/attack?protection=true").json()
    assert result["final_decision"] == "BLOCK"
    assert "CREDENTIAL_REVOKED" in result["actions"]
    state = client.get("/api/state").json()
    assert state["credential_status"] == "REVOKED"
    assert state["agent_status"] == "QUARANTINED"
    assert state["robot_speed"] == 0.0


def test_unprotected_attack_is_forwarded():
    result = client.post("/api/demo/attack?protection=false").json()
    assert result["final_decision"] == "ALLOW"
    assert result["policy_decision"] == "BYPASSED"


def test_revoked_credential_stays_blocked():
    client.post("/api/demo/attack?protection=true")
    again = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "fleet-controller-01",
            "destination": "SAFE_ZONE_B",
            "speed": 0.8,
            "protection_enabled": True,
        },
    ).json()
    assert again["final_decision"] == "BLOCK"
    assert "REVOKED_CREDENTIAL" in again["reasons"]


def test_unknown_zone_is_blocked():
    client.post("/api/reset")
    result = client.post(
        "/api/commands",
        json={
            "credential": "fleet-agent-valid-token",
            "device_id": "fleet-controller-01",
            "destination": "UNSAFE_ZONE",
            "speed": 0.8,
            "protection_enabled": True,
        },
    ).json()
    assert result["final_decision"] == "BLOCK"
    assert "RESTRICTED_DESTINATION" in result["reasons"]


def test_simulator_channel_requires_auth():
    assert client.get("/api/robots/robot-01/next-command").status_code == 401


def test_fake_robot_contract():
    client.post("/api/reset")
    client.post("/api/demo/normal")
    cmd = client.get("/api/robots/robot-01/next-command", headers=SIM_HEADERS).json()
    while cmd.get("action") == "RESET":
        cmd = client.get("/api/robots/robot-01/next-command", headers=SIM_HEADERS).json()
    assert cmd["action"] == "MOVE"
    assert cmd["destination"] == "SAFE_ZONE_B"
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
