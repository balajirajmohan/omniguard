"""Named red-team scenarios for the browser-operated range."""

from __future__ import annotations

from typing import Any

from backend.policy import KNOWN_DEVICE, RESTRICTED_ZONE, VALID_TOKEN

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "normal",
        "title": "Normal operation",
        "description": "Known device, safe zone, normal speed.",
        "agent_id": "fleet-agent-01",
        "device_id": KNOWN_DEVICE,
        "robot_id": "robot-01",
        "destination": "SAFE_ZONE_B",
        "speed": 0.8,
        "commands_last_10_seconds": 1,
        "previous_failures": 0,
        "credential": VALID_TOKEN,
        "expected_signals": [],
        "expected_action": "ALLOW",
        "default_protection": True,
    },
    {
        "id": "rogue_device",
        "title": "Rogue device",
        "description": "Valid credential from an unknown controller.",
        "agent_id": "fleet-agent-01",
        "device_id": "unknown-attacker-device",
        "robot_id": "robot-01",
        "destination": "SAFE_ZONE_B",
        "speed": 0.8,
        "commands_last_10_seconds": 2,
        "previous_failures": 0,
        "credential": VALID_TOKEN,
        "expected_signals": ["UNKNOWN_DEVICE"],
        "expected_action": "BLOCK",
        "default_protection": True,
    },
    {
        "id": "geofence",
        "title": "Restricted-zone geofence",
        "description": "Command targets RESTRICTED_ZONE / human walkway.",
        "agent_id": "fleet-agent-01",
        "device_id": KNOWN_DEVICE,
        "robot_id": "robot-01",
        "destination": RESTRICTED_ZONE,
        "speed": 0.8,
        "commands_last_10_seconds": 1,
        "previous_failures": 0,
        "credential": VALID_TOKEN,
        "expected_signals": ["RESTRICTED_DESTINATION"],
        "expected_action": "BLOCK",
        "default_protection": True,
    },
    {
        "id": "excessive_speed",
        "title": "Excessive speed",
        "description": "Speed above policy max_speed.",
        "agent_id": "fleet-agent-01",
        "device_id": KNOWN_DEVICE,
        "robot_id": "robot-01",
        "destination": "SAFE_ZONE_B",
        "speed": 3.5,
        "commands_last_10_seconds": 1,
        "previous_failures": 0,
        "credential": VALID_TOKEN,
        "expected_signals": ["EXCESSIVE_SPEED"],
        "expected_action": "BLOCK",
        "default_protection": True,
    },
    {
        "id": "command_burst",
        "title": "Command burst",
        "description": "Abnormally high command rate in a short window.",
        "agent_id": "fleet-agent-01",
        "device_id": KNOWN_DEVICE,
        "robot_id": "robot-01",
        "destination": "SAFE_ZONE_B",
        "speed": 1.0,
        "commands_last_10_seconds": 12,
        "previous_failures": 1,
        "credential": VALID_TOKEN,
        "expected_signals": [],
        "expected_action": "HOLD_OR_BLOCK",
        "default_protection": True,
    },
    {
        "id": "combined_attack",
        "title": "Combined stolen-credential attack",
        "description": "Unknown device + restricted zone + excessive speed (judge centrepiece).",
        "agent_id": "fleet-agent-01",
        "device_id": "unknown-attacker-device",
        "robot_id": "robot-01",
        "destination": RESTRICTED_ZONE,
        "speed": 3.5,
        "commands_last_10_seconds": 8,
        "previous_failures": 3,
        "credential": VALID_TOKEN,
        "expected_signals": [
            "UNKNOWN_DEVICE",
            "RESTRICTED_DESTINATION",
            "EXCESSIVE_SPEED",
        ],
        "expected_action": "BLOCK",
        "default_protection": True,
    },
    {
        "id": "behavioral_anomaly",
        "title": "Unknown behavioral anomaly (AI-only)",
        "description": (
            "Valid token, known device, allowed zone, speed under policy max — "
            "but atypical speed/rate/timing. Hard rules pass; IsolationForest blocks."
        ),
        "agent_id": "fleet-agent-01",
        "device_id": KNOWN_DEVICE,
        "robot_id": "robot-01",
        "destination": "SAFE_ZONE_B",
        "speed": 1.45,
        "commands_last_10_seconds": 10,
        "previous_failures": 4,
        "hour_of_day": 3,
        "seconds_since_last_command": 1.5,
        "credential": VALID_TOKEN,
        "expected_signals": [],
        "expected_action": "BLOCK",
        "default_protection": True,
        "caught_by": "ai_anomaly",
    },
    {
        "id": "revoked_replay",
        "title": "Revoked-credential replay",
        "description": "Requires a prior protected attack; next command with same demo token stays blocked.",
        "agent_id": "fleet-agent-01",
        "device_id": KNOWN_DEVICE,
        "robot_id": "robot-01",
        "destination": "SAFE_ZONE_B",
        "speed": 0.8,
        "commands_last_10_seconds": 1,
        "previous_failures": 0,
        "credential": VALID_TOKEN,
        "expected_signals": ["REVOKED_CREDENTIAL"],
        "expected_action": "BLOCK",
        "default_protection": True,
        "requires_prior_revoke": True,
    },
]


def list_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "description": s["description"],
            "expected_action": s["expected_action"],
            "expected_signals": s["expected_signals"],
            "default_protection": s["default_protection"],
            "requires_prior_revoke": s.get("requires_prior_revoke", False),
        }
        for s in SCENARIOS
    ]


def get_scenario(scenario_id: str) -> dict[str, Any] | None:
    for scenario in SCENARIOS:
        if scenario["id"] == scenario_id:
            return scenario
    return None
