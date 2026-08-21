"""Fleet agent behaving normally: valid token, correct device, permitted zone."""
import uuid

import requests

BROKER_URL = "http://localhost:8000"

FLEET_AGENT_CLAIMS = {
    "sub": "fleet-agent-01",
    "robots": ["robot-01"],
    "zones": ["ZONE_A", "ZONE_B"],
    "max_speed": 1.5,
    "device_id": "controller-01",
    "human_zone_authorized": False,
    "ttl_seconds": 3600,
}


def get_token() -> str:
    resp = requests.post(f"{BROKER_URL}/token", json=FLEET_AGENT_CLAIMS)
    resp.raise_for_status()
    return resp.json()["token"]


def send_command(token: str, target_zone: str, x: float, y: float, speed: float):
    payload = {
        "token": token,
        "command_id": str(uuid.uuid4()),
        "robot_id": "robot-01",
        "device_id": "controller-01",
        "target_zone": target_zone,
        "target_x": x,
        "target_y": y,
        "speed": speed,
    }
    resp = requests.post(f"{BROKER_URL}/command", json=payload)
    print(resp.status_code, resp.json())
    return resp.json()


if __name__ == "__main__":
    token = get_token()
    print("Issued token for fleet-agent-01\n")

    print("Moving robot-01 from ZONE_A to ZONE_B at speed 1.0 ...")
    send_command(token, "ZONE_B", x=10.0, y=4.0, speed=1.0)
