"""Deterministic Zero-Trust policy for robot movement commands.

Demo credential is a shared secret for the four-button laptop path.
For signed, expiring credentials use broker/ (JWT) on :8001.
"""

from __future__ import annotations

import os
from typing import Any

# Override in .env for anything beyond a private laptop demo.
VALID_TOKEN = os.getenv("OMNIGUARD_DEMO_TOKEN", "fleet-agent-valid-token")
KNOWN_DEVICE = "fleet-controller-01"
AUTHORIZED_AGENT = "fleet-agent-01"
AUTHORIZED_ROBOT = "robot-01"
RESTRICTED_ZONE = "RESTRICTED_ZONE"
SAFE_ZONES = {"SAFE_ZONE_A", "SAFE_ZONE_B"}
MAX_SPEED = 1.5

HARD_VIOLATIONS = {
    "INVALID_CREDENTIAL",
    "REVOKED_CREDENTIAL",
    "UNAUTHORIZED_AGENT",
    "UNAUTHORIZED_ROBOT",
    "UNKNOWN_DEVICE",
    "RESTRICTED_DESTINATION",
    "EXCESSIVE_SPEED",
}

# When false, AI scores but does not block (shadow mode).
AI_ENFORCE = os.getenv("OMNIGUARD_AI_ENFORCE", "true").lower() not in {
    "0",
    "false",
    "no",
}


def collect_reasons(
    *,
    credential: str,
    credential_status: str,
    agent_id: str,
    device_id: str,
    robot_id: str,
    destination: str,
    speed: float,
) -> list[str]:
    reasons: list[str] = []
    if credential != VALID_TOKEN:
        reasons.append("INVALID_CREDENTIAL")
    if credential_status != "ACTIVE":
        reasons.append("REVOKED_CREDENTIAL")
    if agent_id != AUTHORIZED_AGENT:
        reasons.append("UNAUTHORIZED_AGENT")
    if robot_id != AUTHORIZED_ROBOT:
        reasons.append("UNAUTHORIZED_ROBOT")
    if device_id != KNOWN_DEVICE:
        reasons.append("UNKNOWN_DEVICE")
    # Allowlist: anything outside declared safe zones is restricted.
    if destination not in SAFE_ZONES:
        reasons.append("RESTRICTED_DESTINATION")
    if speed > MAX_SPEED:
        reasons.append("EXCESSIVE_SPEED")
    return reasons


def decide(
    *,
    protection_enabled: bool,
    reasons: list[str],
    risk: float,
) -> dict[str, Any]:
    """Apply runbook decision scheme.

    Hard policy violation -> BLOCK regardless of AI
    AI risk >= 0.80       -> BLOCK and contain
    AI risk 0.60-0.79     -> HOLD
    AI risk < 0.60        -> ALLOW
    Protection OFF        -> ALLOW (forward without policy)
    """
    hard_violation = any(r in HARD_VIOLATIONS for r in reasons)

    if not protection_enabled:
        return {
            "final_decision": "ALLOW",
            "policy_decision": "BYPASSED",
            "actions": ["COMMAND_FORWARDED_WITHOUT_PROTECTION"],
            "contain": False,
        }

    if hard_violation:
        return {
            "final_decision": "BLOCK",
            "policy_decision": "DENY",
            "actions": [
                "COMMAND_REJECTED",
                "CONTAINMENT_REQUESTED",
                "CREDENTIAL_REVOKED",
                "AGENT_QUARANTINED",
            ],
            "contain": True,
        }

    if risk >= 0.80:
        if not AI_ENFORCE:
            return {
                "final_decision": "ALLOW",
                "policy_decision": "AI_SHADOW_ALERT",
                "actions": [
                    "COMMAND_FORWARDED",
                    "AI_ANOMALY_DETECTED_SHADOW",
                ],
                "contain": False,
            }
        return {
            "final_decision": "BLOCK",
            "policy_decision": "REVIEW_AI_RISK",
            "actions": [
                "COMMAND_REJECTED",
                "CONTAINMENT_REQUESTED",
                "CREDENTIAL_REVOKED",
                "AGENT_QUARANTINED",
                "AI_ANOMALY_CONTAINMENT",
            ],
            "contain": True,
        }

    if risk >= 0.60:
        return {
            "final_decision": "HOLD",
            "policy_decision": "HOLD_FOR_REVIEW",
            "actions": ["COMMAND_HELD", "OPERATOR_REVIEW_REQUIRED", "AI_WARNING"],
            "contain": False,
        }

    return {
        "final_decision": "ALLOW",
        "policy_decision": "PERMIT",
        "actions": ["COMMAND_VERIFIED", "COMMAND_FORWARDED"],
        "contain": False,
    }
