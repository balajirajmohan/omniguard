"""Attack scenario: a technically valid stolen token replayed from a rogue
controller, requesting movement into the restricted HUMAN_ZONE.

Run scripts/normal_client.py first (or this script) to have a live token to
steal — in a real attack the token would be exfiltrated from the legitimate
controller's memory/logs/network traffic. Here we just mint one directly to
stand in for that theft, since demonstrating exfiltration itself is out of
scope for the MVP.
"""
import uuid

import requests

BROKER_URL = "http://localhost:8000"

STOLEN_TOKEN_CLAIMS = {
    "sub": "fleet-agent-01",
    "robots": ["robot-01"],
    "zones": ["ZONE_A", "ZONE_B"],
    "max_speed": 1.5,
    "device_id": "controller-01",
    "human_zone_authorized": False,
    "ttl_seconds": 3600,
}

ROGUE_DEVICE_ID = "rogue-controller"
RESTRICTED_ZONE = "HUMAN_ZONE"


def get_stolen_token() -> str:
    resp = requests.post(f"{BROKER_URL}/token", json=STOLEN_TOKEN_CLAIMS)
    resp.raise_for_status()
    return resp.json()["token"]


def send_command(token: str, device_id: str, target_zone: str, x: float, y: float, speed: float):
    payload = {
        "token": token,
        "command_id": str(uuid.uuid4()),
        "robot_id": "robot-01",
        "device_id": device_id,
        "target_zone": target_zone,
        "target_x": x,
        "target_y": y,
        "speed": speed,
    }
    resp = requests.post(f"{BROKER_URL}/command", json=payload)
    print(resp.status_code, resp.json())
    return resp.json()


if __name__ == "__main__":
    token = get_stolen_token()
    print("Attacker has a technically valid stolen token for fleet-agent-01\n")

    print(f"Attempting to move robot-01 into {RESTRICTED_ZONE} from '{ROGUE_DEVICE_ID}' ...")
    first = send_command(token, ROGUE_DEVICE_ID, RESTRICTED_ZONE, x=2.0, y=1.0, speed=1.0)
    assert first["decision"] == "DENY"

    print("\nRetrying with the same (now revoked) token to prove containment holds ...")
    second = send_command(token, ROGUE_DEVICE_ID, RESTRICTED_ZONE, x=2.0, y=1.0, speed=1.0)
    assert second["decision"] == "DENY"
    print("\nCredential stays revoked. Attack contained.")
