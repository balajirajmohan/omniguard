"""Allowlisted read-only investigation tools — no physical or credential control."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.action_history import action_history
from backend.incident_store import incident_store
from backend.containment import PLAYBOOKS


class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str
    seconds: float = Field(default=300, ge=1, le=3600)


class DeviceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str
    seconds: float = Field(default=300, ge=1, le=3600)


class SessionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    seconds: float = Field(default=300, ge=1, le=3600)


class IncidentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str | None = None


class PlaybookArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "get_identity_history": IdentityArgs,
    "get_device_history": DeviceArgs,
    "get_action_sequence": SessionArgs,
    "get_robot_state": EmptyArgs,
    "get_manipulator_state": EmptyArgs,
    "get_zone_context": EmptyArgs,
    "get_model_evidence": IncidentArgs,
    "find_related_incidents": EmptyArgs,
    "retrieve_response_playbook": PlaybookArgs,
}


class InvestigationToolbelt:
    def __init__(self, state_provider: Callable[[], dict[str, Any]]):
        self._state_provider = state_provider

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        schema = TOOL_SCHEMAS.get(name)
        if schema is None:
            return {"ok": False, "error": "UNKNOWN_OR_DISALLOWED_TOOL", "tool": name}
        try:
            args = schema.model_validate(arguments or {})
        except ValidationError as exc:
            return {"ok": False, "error": "INVALID_ARGUMENTS", "detail": exc.errors()}

        handler = getattr(self, name, None)
        if handler is None:
            return {"ok": False, "error": "UNIMPLEMENTED", "tool": name}
        return {"ok": True, "tool": name, "result": handler(args)}

    def get_identity_history(self, args: IdentityArgs) -> Any:
        events = action_history.recent_for_identity(args.agent_id, args.seconds)
        return [e.sanitized_dict() for e in events[-50:]]

    def get_device_history(self, args: DeviceArgs) -> Any:
        # Filter identity history by device from recent robot stream.
        events = [
            e
            for e in action_history.recent_for_robot("robot-01", args.seconds)
            if e.device_id == args.device_id
        ]
        return [e.sanitized_dict() for e in events[-50:]]

    def get_action_sequence(self, args: SessionArgs) -> Any:
        events = action_history.recent_for_session(args.session_id, args.seconds)
        return [e.sanitized_dict() for e in events[-50:]]

    def get_robot_state(self, _args: EmptyArgs) -> Any:
        state = self._state_provider()
        bridge = state.get("isaac_bridge_state") or state.get("mock_bridge_state") or {}
        return {
            "robot_status": state.get("robot_status"),
            "robot_zone": state.get("robot_zone"),
            "robot_speed": state.get("robot_speed"),
            "position": bridge.get("position"),
            "motion_state": bridge.get("motion_state"),
        }

    def get_manipulator_state(self, _args: EmptyArgs) -> Any:
        state = self._state_provider()
        bridge = state.get("isaac_bridge_state") or state.get("mock_bridge_state") or {}
        return {"arm": bridge.get("arm"), "gripper": bridge.get("gripper")}

    def get_zone_context(self, _args: EmptyArgs) -> Any:
        from backend.zones import teleop_config_payload

        return teleop_config_payload()

    def get_model_evidence(self, args: IncidentArgs) -> Any:
        if args.incident_id:
            incident = incident_store.get(args.incident_id)
            return (incident or {}).get("ai_evidence")
        incidents = incident_store.list(limit=1)
        return (incidents[0] if incidents else {}).get("ai_evidence")

    def find_related_incidents(self, _args: EmptyArgs) -> Any:
        return [
            {
                "incident_id": i["incident_id"],
                "status": i["status"],
                "playbook": i.get("playbook"),
                "event_count": i.get("event_count"),
            }
            for i in incident_store.list(limit=10)
        ]

    def retrieve_response_playbook(self, args: PlaybookArgs) -> Any:
        ops = PLAYBOOKS.get(args.name)
        if not ops:
            return {"error": "UNKNOWN_PLAYBOOK"}
        return {
            "name": args.name,
            "operations": ops,
            "note": "Proposal only — ContainmentExecutor must validate and run.",
        }
