from fastapi.testclient import TestClient

from backend.main import SIMULATOR_TOKEN, app

client = TestClient(app)
SIM_HEADERS = {"X-OmniGuard-Simulator": SIMULATOR_TOKEN}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


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
