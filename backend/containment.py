"""Allowlisted deterministic containment — LLMs never call this directly.

Physical truth: the authenticated Isaac bridge /stop clears queued motion and
stops the base. It does NOT prove arm halt or a safe gripper pose. Those remain
REQUESTED/UNVERIFIED until explicit telemetry confirms them.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from backend.actuation import ActuationResult, maybe_actuate_stop

ALLOWED_OPERATIONS = {
    "REJECT_COMMAND",
    "ROBOT_ESTOP_REQUESTED",
    "STOP_BASE",
    "STOP_ARM",
    "SAFE_GRIPPER",
    "TERMINATE_SESSION",
    "REVOKE_CREDENTIAL",
    "QUARANTINE_DEVICE",
    "QUARANTINE_AGENT",
}

# Operations that a generic /stop can honestly satisfy when the bridge accepts it.
ESTOP_PROVES = {"ROBOT_ESTOP_REQUESTED", "STOP_BASE"}
# Require explicit manipulator telemetry before these can be acknowledged.
NEEDS_TELEMETRY = {"STOP_ARM", "SAFE_GRIPPER"}

PLAYBOOKS: dict[str, list[str]] = {
    "SINGLE_UNSAFE_COMMAND": [
        "REJECT_COMMAND",
        "ROBOT_ESTOP_REQUESTED",
        "STOP_BASE",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_AGENT",
    ],
    "SUSPICIOUS_SESSION": [
        "REJECT_COMMAND",
        "ROBOT_ESTOP_REQUESTED",
        "TERMINATE_SESSION",
    ],
    "CREDENTIAL_COMPROMISE": [
        "REJECT_COMMAND",
        "ROBOT_ESTOP_REQUESTED",
        "STOP_BASE",
        "STOP_ARM",
        "SAFE_GRIPPER",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_AGENT",
        "QUARANTINE_DEVICE",
    ],
    "ROGUE_DEVICE": [
        "REJECT_COMMAND",
        "ROBOT_ESTOP_REQUESTED",
        "STOP_BASE",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_DEVICE",
        "QUARANTINE_AGENT",
    ],
    "UNSAFE_MANIPULATION_SEQUENCE": [
        "REJECT_COMMAND",
        "ROBOT_ESTOP_REQUESTED",
        "STOP_BASE",
        "STOP_ARM",
        "SAFE_GRIPPER",
        "TERMINATE_SESSION",
        "REVOKE_CREDENTIAL",
        "QUARANTINE_AGENT",
    ],
    "CRITICAL_PHYSICAL_RISK": [
        "REJECT_COMMAND",
        "ROBOT_ESTOP_REQUESTED",
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
        manipulator_telemetry: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._apply_identity = apply_identity_containment
        self._terminate_session = terminate_session
        self._manipulator_telemetry = manipulator_telemetry
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
                "unverified": [],
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
                    "unverified": [],
                    "failed": [op],
                }

        requested = list(ops)
        attempted: list[str] = []
        acknowledged: list[str] = []
        unverified: list[str] = []
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

            if "REJECT_COMMAND" in ops:
                attempted.append("REJECT_COMMAND")
                acknowledged.append("REJECT_COMMAND")

            needs_estop = bool(set(ops) & (ESTOP_PROVES | NEEDS_TELEMETRY))
            if needs_estop:
                for op in ops:
                    if op in ESTOP_PROVES or op in NEEDS_TELEMETRY:
                        if op not in attempted:
                            attempted.append(op)
                actuation = maybe_actuate_stop(robot_id)
                ack = self._ack_from_actuation(actuation)
                bridge_acks.append(ack)
                estop_ok = ack.get("stage") in {"EXECUTED", "QUEUED", "MOCK_SKIPPED"} and ack.get(
                    "ok", True
                )
                if estop_ok:
                    # Honest claim: we requested an authenticated robot E-stop and
                    # the bridge accepted/queued it (or mock skipped). That proves
                    # base stop intent — not arm/gripper safe state.
                    if "ROBOT_ESTOP_REQUESTED" in ops:
                        acknowledged.append("ROBOT_ESTOP_REQUESTED")
                    elif "STOP_BASE" in ops:
                        acknowledged.append("ROBOT_ESTOP_REQUESTED")
                    if "STOP_BASE" in ops:
                        acknowledged.append("STOP_BASE")
                    for op in NEEDS_TELEMETRY:
                        if op not in ops:
                            continue
                        if self._telemetry_confirms(op):
                            acknowledged.append(op)
                        else:
                            unverified.append(op)
                else:
                    failed.append("ROBOT_ESTOP_REQUESTED")
                    for op in ops:
                        if op in ESTOP_PROVES or op in NEEDS_TELEMETRY:
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
            "unverified": unverified,
            "failed": failed,
            "bridge_acknowledgements": bridge_acks,
            "note": (
                "ROBOT_ESTOP_REQUESTED/STOP_BASE reflect authenticated /stop. "
                "STOP_ARM and SAFE_GRIPPER stay UNVERIFIED without manipulator telemetry."
            ),
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self.last_result = result
        return result

    def _telemetry_confirms(self, op: str) -> bool:
        if self._manipulator_telemetry is None:
            return False
        try:
            state = self._manipulator_telemetry() or {}
        except Exception:  # noqa: BLE001
            return False
        if op == "STOP_ARM":
            arm = state.get("arm") or {}
            return arm.get("motion_state") in {"STOPPED", "IDLE", "STOWED"}
        if op == "SAFE_GRIPPER":
            grip = state.get("gripper") or {}
            return grip.get("action") in {"open", "safe"} or grip.get("safe") is True
        return False

    def _ack_from_actuation(self, actuation: ActuationResult | None) -> dict[str, Any]:
        if actuation is None:
            return {
                "stage": "MOCK_SKIPPED",
                "command_id": None,
                "ok": True,
                "proves": sorted(ESTOP_PROVES),
            }
        return {
            "stage": actuation.stage,
            "command_id": actuation.command_id,
            "ok": actuation.ok,
            "detail": actuation.detail,
            "proves": sorted(ESTOP_PROVES),
        }


containment_executor = ContainmentExecutor()
