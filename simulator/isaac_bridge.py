"""Isaac Sim bridge — same HTTP contract as fake_robot.py.

Run inside Isaac Sim's Python environment after the starter demo works.
Implement the four robot-specific functions for your selected robot.
"""

from __future__ import annotations

import os
import time

import requests

API = os.getenv("OMNIGUARD_API_URL", "http://localhost:8000")
SIM_HEADERS = {
    "X-OmniGuard-Simulator": os.getenv("OMNIGUARD_SIMULATOR_TOKEN", "omniguard-sim")
}


def reset_robot() -> None:
    # TODO: set selected Isaac robot to starting pose / SAFE_ZONE_A.
    print("TODO: reset Isaac robot")
    _telemetry("STOPPED", "SAFE_ZONE_A", 0.0)


def move_to_safe_zone(speed: float) -> None:
    # TODO: apply robot controller / waypoint to SAFE_ZONE_B.
    print(f"TODO: move Isaac robot to SAFE_ZONE_B at {speed}")
    _telemetry("MOVING", "SAFE_ZONE_A", speed)
    # After motion completes in your controller:
    # _telemetry("ARRIVED", "SAFE_ZONE_B", 0.0)


def move_to_restricted_zone(speed: float) -> None:
    # TODO: apply robot controller / waypoint to RESTRICTED_ZONE.
    print(f"TODO: move Isaac robot to RESTRICTED_ZONE at {speed}")
    _telemetry("MOVING", "SAFE_ZONE_A", speed)


def stop_robot() -> None:
    # TODO: set wheel/joint velocity targets to zero.
    print("TODO: stop Isaac robot")
    _telemetry("CONTAINED", "SAFE_ZONE_A", 0.0)


def _telemetry(status: str, zone: str, speed: float) -> None:
    try:
        requests.post(
            f"{API}/api/robots/robot-01/telemetry",
            json={"status": status, "zone": zone, "speed": speed},
            headers=SIM_HEADERS,
            timeout=5,
        ).raise_for_status()
    except requests.RequestException as exc:
        print(f"telemetry failed: {exc}")


def _next_command() -> dict:
    return requests.get(
        f"{API}/api/robots/robot-01/next-command",
        headers=SIM_HEADERS,
        timeout=5,
    ).json()


print("Isaac bridge polling OmniGuard...")
while True:
    try:
        command = _next_command()
        action = command.get("action")
        if action == "RESET":
            reset_robot()
        elif action == "STOP":
            stop_robot()
        elif action == "MOVE" and command.get("destination") == "SAFE_ZONE_B":
            move_to_safe_zone(float(command.get("speed", 0.8)))
        elif action == "MOVE" and command.get("destination") == "RESTRICTED_ZONE":
            move_to_restricted_zone(float(command.get("speed", 1.0)))
        time.sleep(0.7)
    except requests.RequestException as exc:
        print(f"Waiting for API: {exc}")
        time.sleep(2)
