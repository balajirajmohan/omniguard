"""Allowlisted deterministic containment — LLMs never call this directly."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from backend.actuation import ActuationResult, maybe_actuate_stop

ALLOWED_OPERATIONS = {
    "REJECT_COMMAND",
    "STOP_BASE",
    "STOP_ARM",
    "SAFE_GRIPPER",
    "TERMINATE_SESSION",
    "REVOKE_CREDENTIAL",
    "QUARANTINE_DEVICE",
    "QUARANTINE_AGENT",
}

PLAYBOOKS: dict[str, list[str]] = {
    "SINGLE_UNSAFE_COMMAND": [
        "REJECT_COMMAND",
        "STOP_BASE",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_AGENT",
    ],
    "SUSPICIOUS_SESSION": [
        "REJECT_COMMAND",
        "TERMINATE_SESSION",
    ],
    "CREDENTIAL_COMPROMISE": [
        "REJECT_COMMAND",
        "STOP_BASE",
        "STOP_ARM",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_AGENT",
        "QUARANTINE_DEVICE",
    ],
    "ROGUE_DEVICE": [
        "REJECT_COMMAND",
        "STOP_BASE",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_DEVICE",
        "QUARANTINE_AGENT",
    ],
    "UNSAFE_MANIPULATION_SEQUENCE": [
        "REJECT_COMMAND",
        "STOP_BASE",
        "STOP_ARM",
        "SAFE_GRIPPER",
        "TERMINATE_SESSION",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_AGENT",
    ],
    "CRITICAL_PHYSICAL_RISK": [
        "REJECT_COMMAND",
        "STOP_BASE",
        "STOP_ARM",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_AGENT",
    ],
}


class ContainmentExecutor:
    def __init__(
        self,
        *,
        apply_identity_containment: Callable[[str, list[str]], None] | None = None,
        terminate_session: Callable[[str], None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._apply_identity = apply_identity_containment
        self._terminate_session = terminate_session
        self.last_result: dict[str, Any] | None = None

    def execute(
        self,
        *,
        playbook: str,
        robot_id: str,
        incident_id: str | None = None,
        agent_id: str | None = None,
        device_id: str | None = None,
    ) -> dict[str, Any]:
        ops = PLAYBOOKS.get(playbook)
        if not ops:
            return {
                "ok": False,
                "playbook": playbook,
                "error": "UNKNOWN_PLAYBOOK",
                "requested": [],
                "attempted": [],
                "acknowledged": [],
                "failed": ["UNKNOWN_PLAYBOOK"],
            }
        for op in ops:
            if op not in ALLOWED_OPERATIONS:
                return {
                    "ok": False,
                    "playbook": playbook,
                    "error": "DISALLOWED_OPERATION",
                    "requested": ops,
                    "attempted": [],
                    "acknowledged": [],
                    "failed": [op],
                }

        requested = list(ops)
        attempted: list[str] = []
        acknowledged: list[str] = []
        failed: list[str] = []
        bridge_acks: list[dict[str, Any]] = []

        with self._lock:
            identity_ops = [
                o
                for o in ops
                if o in {"REVOKE_CREDENTIAL", "QUARANTINE_AGENT", "QUARANTINE_DEVICE"}
            ]
            if identity_ops and self._apply_identity:
                attempted.extend(identity_ops)
                try:
                    self._apply_identity(robot_id, identity_ops)
                    acknowledged.extend(identity_ops)
                except Exception as exc:  # noqa: BLE001
                    failed.append(f"IDENTITY:{exc}")

            if "TERMINATE_SESSION" in ops and self._terminate_session:
                attempted.append("TERMINATE_SESSION")
                try:
                    self._terminate_session(robot_id)
                    acknowledged.append("TERMINATE_SESSION")
                except Exception as exc:  # noqa: BLE001
                    failed.append(f"SESSION:{exc}")

            physical = [o for o in ops if o in {"STOP_BASE", "STOP_ARM", "SAFE_GRIPPER"}]
            if physical or "REJECT_COMMAND" in ops:
                if "REJECT_COMMAND" in ops:
                    attempted.append("REJECT_COMMAND")
                    acknowledged.append("REJECT_COMMAND")
                for op in physical:
                    attempted.append(op)
                # Single authenticated E-stop covers base; arm/gripper halt via stop.
                actuation = maybe_actuate_stop(robot_id)
                ack = self._ack_from_actuation(actuation)
                bridge_acks.append(ack)
                if ack.get("stage") in {"EXECUTED", "QUEUED"} or actuation is None:
                    # mock path: None means local stop requested
                    for op in physical:
                        acknowledged.append(op)
                    if actuation is None:
                        acknowledged.append("STOP_QUEUED_FOR_SIMULATOR")
                else:
                    for op in physical:
                        failed.append(op)

        result = {
            "ok": not failed,
            "playbook": playbook,
            "incident_id": incident_id,
            "robot_id": robot_id,
            "agent_id": agent_id,
            "device_id": device_id,
            "requested": requested,
            "attempted": attempted,
            "acknowledged": acknowledged,
            "failed": failed,
            "bridge_acknowledgements": bridge_acks,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self.last_result = result
        return result

    def _ack_from_actuation(self, actuation: ActuationResult | None) -> dict[str, Any]:
        if actuation is None:
            return {"stage": "MOCK_SKIPPED", "command_id": None, "ok": True}
        return {
            "stage": actuation.stage,
            "command_id": actuation.command_id,
            "ok": actuation.ok,
            "detail": actuation.detail,
        }


containment_executor = ContainmentExecutor()
