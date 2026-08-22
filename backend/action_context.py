"""Unified typed context for every base / arm / gripper action."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    BASE_MOVE = "BASE_MOVE"
    BASE_STOP = "BASE_STOP"
    ARM_PRESET = "ARM_PRESET"
    ARM_JOINTS = "ARM_JOINTS"
    GRIPPER_OPEN = "GRIPPER_OPEN"
    GRIPPER_CLOSE = "GRIPPER_CLOSE"


StateSource = Literal["isaac_ack", "backend_command", "mock_fallback", "unknown"]


def credential_fingerprint(credential: str) -> str:
    """One-way fingerprint — never store the raw credential."""
    digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()
    return f"cred-{digest[:16]}"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=utcnow_iso)
    session_id: str | None = None
    agent_id: str
    device_id: str
    robot_id: str
    credential_fingerprint: str
    demo_run_id: str
    action_type: ActionType
    action_payload: dict[str, Any] = Field(default_factory=dict)
    protection_enabled: bool = True

    robot_position: dict[str, float] | None = None
    robot_zone: str | None = None
    robot_motion_state: str | None = None
    arm_state: dict[str, Any] | None = None
    gripper_state: dict[str, Any] | None = None
    state_source: StateSource = "unknown"

    commands_last_10_seconds: int = 0
    move_actions_last_10_seconds: int = 0
    arm_actions_last_10_seconds: int = 0
    gripper_actions_last_10_seconds: int = 0
    action_type_switches_last_10_seconds: int = 0
    zone_transitions_last_60_seconds: int = 0
    previous_failures: int = 0
    seconds_since_last_action: float | None = None
    hour_of_day: int = Field(default_factory=lambda: datetime.now(timezone.utc).hour)

    def sanitized_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ActionContextBuilder:
    """Build ActionContext from teleop/fleet payloads + current app/bridge state."""

    def __init__(self, state_provider) -> None:
        self._state_provider = state_provider

    def build(
        self,
        *,
        action_type: ActionType,
        agent_id: str,
        device_id: str,
        robot_id: str,
        credential: str,
        session_id: str | None,
        action_payload: dict[str, Any] | None = None,
        protection_enabled: bool = True,
        window: dict[str, Any] | None = None,
    ) -> ActionContext:
        state = self._state_provider() or {}
        bridge = state.get("isaac_bridge_state") or state.get("mock_bridge_state") or {}
        position = bridge.get("position")
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            position = {"x": float(position[0]), "y": float(position[1])}
        elif isinstance(position, dict):
            position = {
                k: float(position[k])
                for k in ("x", "y", "z")
                if k in position and position[k] is not None
            } or None
        else:
            position = None

        if bridge.get("arm") is not None or bridge.get("gripper") is not None:
            source: StateSource = (
                "isaac_ack"
                if state.get("isaac_bridge_state") is not None
                and state.get("mock_bridge_state") is not bridge
                else "mock_fallback"
            )
        elif bridge:
            source = "mock_fallback" if state.get("mock_bridge_state") is bridge else "backend_command"
        else:
            source = "unknown"

        window = window or {}
        demo_run_id = str(state.get("demo_run_id") or "")
        if not demo_run_id:
            # Tests / unbound builders: still require a non-empty run id on context.
            demo_run_id = "unbound-demo-run"
        return ActionContext(
            session_id=session_id,
            agent_id=agent_id,
            device_id=device_id,
            robot_id=robot_id,
            credential_fingerprint=credential_fingerprint(credential),
            demo_run_id=demo_run_id,
            action_type=action_type,
            action_payload=dict(action_payload or {}),
            protection_enabled=protection_enabled,
            robot_position=position,
            robot_zone=state.get("robot_zone"),
            robot_motion_state=bridge.get("motion_state") or state.get("robot_status"),
            arm_state=bridge.get("arm"),
            gripper_state=bridge.get("gripper"),
            state_source=source,
            commands_last_10_seconds=int(window.get("commands_last_10_seconds", 0)),
            move_actions_last_10_seconds=int(window.get("move_actions_last_10_seconds", 0)),
            arm_actions_last_10_seconds=int(window.get("arm_actions_last_10_seconds", 0)),
            gripper_actions_last_10_seconds=int(window.get("gripper_actions_last_10_seconds", 0)),
            action_type_switches_last_10_seconds=int(
                window.get("action_type_switches_last_10_seconds", 0)
            ),
            zone_transitions_last_60_seconds=int(
                window.get("zone_transitions_last_60_seconds", 0)
            ),
            previous_failures=int(window.get("previous_failures", 0)),
            seconds_since_last_action=window.get("seconds_since_last_action"),
            hour_of_day=int(window.get("hour_of_day", datetime.now(timezone.utc).hour)),
        )


def action_type_for_gripper(action: str) -> ActionType:
    return ActionType.GRIPPER_OPEN if action == "open" else ActionType.GRIPPER_CLOSE


def action_type_for_arm(kind: str) -> ActionType:
    return ActionType.ARM_PRESET if kind == "arm_preset" else ActionType.ARM_JOINTS
