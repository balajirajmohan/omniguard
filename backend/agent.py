"""Bounded investigation agent — recommend only, never move robots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

ALLOWED_TOOLS = {
    "get_recent_events",
    "get_identity_state",
    "get_robot_state",
    "get_model_evidence",
    "recommend_containment",
    "create_incident_report",
}

PHYSICAL_ACTIONS = {
    "block_command",
    "emergency_stop",
    "revoke_credential",
    "quarantine_agent",
}


class InvestigationAgent:
    def __init__(self, state_provider: Callable[[], dict[str, Any]]):
        self._state_provider = state_provider

    def run(self, incident: dict[str, Any] | None = None) -> dict[str, Any]:
        timeline: list[dict[str, Any]] = []
        state = self._state_provider()

        def note(tool: str, result: Any) -> Any:
            timeline.append(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "tool": tool,
                    "result_summary": (
                        list(result.keys()) if isinstance(result, dict) else type(result).__name__
                    ),
                }
            )
            return result

        events = note("get_recent_events", list(state.get("events", []))[:5])
        identity = note(
            "get_identity_state",
            {
                "credential_status": state.get("credential_status"),
                "agent_status": state.get("agent_status"),
            },
        )
        robot = note(
            "get_robot_state",
            {
                "robot_status": state.get("robot_status"),
                "robot_zone": state.get("robot_zone"),
                "robot_speed": state.get("robot_speed"),
                "last_containment_ack": state.get("last_containment_ack"),
            },
        )
        evidence = note(
            "get_model_evidence",
            {
                "latest": events[0] if events else incident,
            },
        )
        recommendations = note(
            "recommend_containment",
            {
                "proposed_actions": sorted(PHYSICAL_ACTIONS),
                "note": (
                    "Recommendations only. Deterministic policy must validate "
                    "and execute allowlisted physical actions."
                ),
            },
        )
        report = note(
            "create_incident_report",
            {
                "identity": identity,
                "robot": robot,
                "evidence": evidence,
                "recommendations": recommendations,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "agent": "omniguard-investigation-v1",
            "tools_used": list(ALLOWED_TOOLS),
            "disallowed": ["arbitrary_robot_movement"],
            "timeline": timeline,
            "report": report,
        }
