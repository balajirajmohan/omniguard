from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


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


def test_fake_robot_contract():
    client.post("/api/reset")
    client.post("/api/demo/normal")
    cmd = client.get("/api/robots/robot-01/next-command").json()
    # RESET may still be first after reset_state inside demo_normal
    while cmd.get("action") == "RESET":
        cmd = client.get("/api/robots/robot-01/next-command").json()
    assert cmd["action"] == "MOVE"
    assert cmd["destination"] == "SAFE_ZONE_B"
    ack = client.post(
        "/api/robots/robot-01/telemetry",
        json={"status": "ARRIVED", "zone": "SAFE_ZONE_B", "speed": 0.0},
    )
    assert ack.status_code == 200
