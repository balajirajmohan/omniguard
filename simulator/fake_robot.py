from __future__ import annotations

import os
import time

import requests

API = os.getenv("OMNIGUARD_API_URL", "http://localhost:8000")


def send_telemetry(status: str, zone: str, speed: float = 0.0) -> None:
    requests.post(
        f"{API}/api/robots/robot-01/telemetry",
        json={"status": status, "zone": zone, "speed": speed},
        timeout=5,
    ).raise_for_status()


print("Fake robot started. Waiting for OmniGuard commands...")
zone = "SAFE_ZONE_A"

while True:
    try:
        command = requests.get(
            f"{API}/api/robots/robot-01/next-command", timeout=5
        ).json()
        action = command.get("action")

        if action == "RESET":
            zone = "SAFE_ZONE_A"
            send_telemetry("STOPPED", zone, 0.0)
            print("RESET -> robot returned to SAFE_ZONE_A")
        elif action == "MOVE":
            destination = command["destination"]
            speed = command["speed"]
            send_telemetry("MOVING", zone, speed)
            print(f"MOVE -> {destination} at speed {speed}")
            if destination == "RESTRICTED_ZONE":
                print("DANGER: unprotected robot is entering the human zone!")
            time.sleep(2)
            zone = destination
            send_telemetry("ARRIVED", zone, 0.0)
            print(f"ARRIVED -> {zone}")
        elif action == "STOP":
            send_telemetry("CONTAINED", zone, 0.0)
            print("STOP -> robot contained by OmniGuard")

        time.sleep(0.7)
    except requests.RequestException as exc:
        print(f"Waiting for API: {exc}")
        time.sleep(2)
