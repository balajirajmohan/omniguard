"""Bounded investigation agent — recommend only, never move robots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from backend.investigation_tools import InvestigationToolbelt
from backend.risk_policy import risk_policy

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
        self._tools = InvestigationToolbelt(state_provider)

    def run(self, incident: dict[str, Any] | None = None) -> dict[str, Any]:
        """Deterministic v1 workflow retained for /api/investigate compatibility."""
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
            {"latest": events[0] if events else incident},
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

    def run_v2(self, incident: dict[str, Any] | None = None) -> dict[str, Any]:
        """Read-only tool-using investigation. Never executes containment."""
        max_rounds = int(
            (risk_policy.raw.get("llm") or {}).get("max_agent_rounds", 5)
        )
        incident = incident or {}
        tools_used: list[str] = []
        evidence: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []

        plan = [
            ("get_robot_state", {}),
            ("get_manipulator_state", {}),
            ("get_zone_context", {}),
            (
                "get_identity_history",
                {"agent_id": incident.get("agent_id") or "fleet-agent-01", "seconds": 300},
            ),
            (
                "get_model_evidence",
                {"incident_id": incident.get("incident_id")},
            ),
            ("find_related_incidents", {}),
            (
                "retrieve_response_playbook",
                {
                    "name": incident.get("playbook")
                    or "UNSAFE_MANIPULATION_SEQUENCE"
                },
            ),
        ]

        for name, args in plan[:max_rounds]:
            result = self._tools.call(name, args)
            tools_used.append(name)
            trace.append(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "tool": name,
                    "arguments": args,
                    "ok": result.get("ok"),
                }
            )
            if result.get("ok"):
                evidence.append({"tool": name, "result": result.get("result")})

        playbook = incident.get("playbook") or "UNSAFE_MANIPULATION_SEQUENCE"
        src = incident.get("decision_source")
        if src in {"action_window_ai", "behavioral_rule", "hybrid_rule_ml", "ai_warning"}:
            hypothesis = (
                "Valid identity issued an individually-legal but collectively abnormal "
                "base/arm/gripper sequence "
                f"(decision_source={src})."
            )
        else:
            hypothesis = (
                "Hard-policy or identity violation produced a containment event."
            )
        return {
            "agent": "omniguard-investigation-v2",
            "mode": "deterministic_fallback",
            "hypothesis": hypothesis,
            "confidence": None,
            "confidence_label": "qualitative_medium",
            "evidence": evidence,
            "tools_used": tools_used,
            "tool_trace": trace,
            "proposed_playbook": playbook,
            "execution_authorized": False,
            "provider": "fallback",
            "model": "deterministic-investigation",
            "fallback_used": True,
            "disallowed": [
                "arbitrary_robot_movement",
                "llm_bridge_control",
                "credential_exfiltration",
            ],
        }
