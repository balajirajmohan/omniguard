"""Central classification: AUDIT_EVENT vs durable INCIDENT."""

from __future__ import annotations

from typing import Any, Literal

RecordKind = Literal["AUDIT_EVENT", "INCIDENT", "CORRELATED_INCIDENT"]

# Routine control-protocol reasons — audit unless repeated past threshold.
AUDIT_ONLY_REASONS = {
    "JOYSTICK_RELEASED",
    "PAGE_BLUR",
    "DEADMAN_TIMEOUT",
    "LEASE_EXPIRED",
    "SEQUENCE_REPLAY",
    "SEQUENCE_OUT_OF_ORDER",
    "STALE_LEASE",
    "OPERATOR_DISCONNECT",
    "SESSION_TERMINATED",
    "RATE_LIMIT",
    "UNKNOWN_OR_MISMATCHED_LEASE",
    "TELEOP_STOP",
    "BASE_STOP",
}

# Hard-policy reasons that always create/correlate a durable incident.
HARD_POLICY_INCIDENT_REASONS = {
    "UNKNOWN_DEVICE",
    "RESTRICTED_DESTINATION",
    "EXCESSIVE_SPEED",
    "REVOKED_CREDENTIAL",
    "UNAUTHORIZED_AGENT",
    "UNAUTHORIZED_ROBOT",
    "INVALID_CREDENTIAL",  # create immediately (documented choice)
}

CONTROL_PROTOCOL_KINDS = {
    "teleop_stop",
    "teleop_deadman",
    "teleop_lease_expired",
    "joystick_release",
}


def playbook_for_hard_reasons(reasons: list[str]) -> str:
    rs = set(reasons)
    identity = rs & {
        "UNKNOWN_DEVICE",
        "UNAUTHORIZED_AGENT",
        "UNAUTHORIZED_ROBOT",
        "REVOKED_CREDENTIAL",
        "INVALID_CREDENTIAL",
    }
    physical = rs & {"RESTRICTED_DESTINATION", "EXCESSIVE_SPEED"}
    if identity and physical:
        return "ROGUE_DEVICE"
    if identity:
        return "CREDENTIAL_COMPROMISE"
    if physical:
        return "CRITICAL_PHYSICAL_RISK"
    return "SINGLE_UNSAFE_COMMAND"


def classify_security_record(event: dict[str, Any]) -> RecordKind:
    """Classify whether an event should open a durable incident.

    Routine control lifecycle → AUDIT_EVENT.
    Security BLOCK with containment, or AI HOLD for review → INCIDENT.
    Escalated repeated audit events (caller sets escalate=True) → INCIDENT.
    """
    if event.get("escalate_to_incident"):
        return "INCIDENT"

    final = str(event.get("final_decision") or "")
    reasons = set(event.get("reasons") or [])
    kind = str(event.get("kind") or "")

    if kind in CONTROL_PROTOCOL_KINDS:
        return "AUDIT_EVENT"
    if reasons and reasons <= AUDIT_ONLY_REASONS:
        return "AUDIT_EVENT"
    if any(r in HARD_POLICY_INCIDENT_REASONS for r in reasons):
        return "INCIDENT"
    if final == "BLOCK":
        return "INCIDENT"
    if final == "HOLD" and (
        event.get("requires_human_review")
        or event.get("response_playbook")
        or event.get("decision_source") in {
            "ai_warning",
            "command_anomaly_ai",
            "action_window_ai",
            "behavioral_rule",
            "hybrid_rule_ml",
        }
    ):
        return "INCIDENT"
    if event.get("requires_incident"):
        return "INCIDENT"
    return "AUDIT_EVENT"
