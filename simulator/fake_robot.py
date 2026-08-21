from __future__ import annotations

import os
import time

import requests

API = os.getenv("OMNIGUARD_API_URL", "http://localhost:8000")
SIM_HEADERS = {
    "X-OmniGuard-Simulator": os.getenv("OMNIGUARD_SIMULATOR_TOKEN", "omniguard-sim")
}


def send_telemetry(status: str, zone: str, speed: float = 0.0) -> None:
    requests.post(
        f"{API}/api/robots/robot-01/telemetry",
        json={"status": status, "zone": zone, "speed": speed},
        headers=SIM_HEADERS,
        timeout=5,
    ).raise_for_status()


def fetch_command() -> dict:
    return requests.get(
        f"{API}/api/robots/robot-01/next-command",
        headers=SIM_HEADERS,
        timeout=5,
    ).json()


def containment_active() -> bool:
    try:
        st = requests.get(f"{API}/api/state", timeout=3).json()
    except requests.RequestException:
        return False
    return st.get("robot_status") in {"CONTAINED", "CONTAINMENT_FAILED"}


def move_interruptible(destination: str, speed: float, zone: str) -> str:
    """Simulate travel while watching for containment; return final zone."""
    send_telemetry("MOVING", zone, speed)
    print(f"MOVE -> {destination} at speed {speed}")
    if destination == "RESTRICTED_ZONE":
        print("DANGER: unprotected robot is entering the human zone!")

    for _ in range(10):  # ~2s total
        time.sleep(0.2)
        if containment_active():
            # Drain STOP if queued so it is not left behind.
            cmd = fetch_command()
            if cmd.get("action") not in {"STOP", "NONE", "RESET"}:
                # Unexpected command while aborting — leave it for next loop
                # by not consuming further; STOP already applied via state.
                pass
            send_telemetry("CONTAINED", zone, 0.0)
            print("STOP mid-move -> robot contained by OmniGuard")
            return zone

    send_telemetry("ARRIVED", destination, 0.0)
    print(f"ARRIVED -> {destination}")
    return destination


print("Fake robot started. Waiting for OmniGuard commands...")
zone = "SAFE_ZONE_A"

while True:
    try:
        command = fetch_command()
        action = command.get("action")

        if action == "RESET":
            zone = "SAFE_ZONE_A"
            send_telemetry("STOPPED", zone, 0.0)
            print("RESET -> robot returned to SAFE_ZONE_A")
        elif action == "MOVE":
            zone = move_interruptible(command["destination"], command["speed"], zone)
        elif action == "STOP":
            send_telemetry("CONTAINED", zone, 0.0)
            print("STOP -> robot contained by OmniGuard")

        time.sleep(0.7)
    except requests.RequestException as exc:
        print(f"Waiting for API: {exc}")
        time.sleep(2)
