"""Backend-mediated teleoperation leases and deadman monitor.

AI scores session start in SHADOW_TELEOP only. Deterministic checks validate
every move packet. The browser never receives bridge credentials.
"""

from __future__ import annotations

import math
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from backend.actuation import (
    maybe_actuate_arm_joints,
    maybe_actuate_arm_preset,
    maybe_actuate_gripper,
    maybe_actuate_move_xy,
    maybe_actuate_stop,
)
from backend.anomaly import detector
from backend.policy import HARD_VIOLATIONS, KNOWN_DEVICE, collect_reasons
from backend.zones import (
    ALLOWED_TELEOP_ZONES,
    ARM_PRESETS,
    GRIPPER_ACTIONS,
    MAX_TELEOP_SPEED,
    is_allowed_teleop_point,
    teleop_config_payload,
)

LEASE_TTL_SECONDS = 30
DEADMAN_TIMEOUT_MS = int(os.getenv("TELEOP_DEADMAN_TIMEOUT_MS", "750"))
MAX_STREAM_HZ = 10
MIN_PACKET_INTERVAL_S = 1.0 / MAX_STREAM_HZ

STOP_CONFIRMED_STAGES = {"EXECUTED", "MOCK_CONFIRMED"}
STOP_ACCEPTED_STAGES = {"EXECUTED", "QUEUED", "MOCK_CONFIRMED", "MOCK_SKIPPED"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def classify_hold_stop(
    actuation: ActuationResult | None,
    *,
    telemetry_confirms_stopped: bool = False,
) -> dict[str, Any]:
    """Map an E-stop attempt into truthful HOLD pause fields.

    robot_stopped is always identical to stop_confirmed.
    """
    stop_requested = True
    if actuation is None:
        # Mock backend: no Isaac call; confirmation comes from local mock state update.
        return {
            "status": "PAUSED_FOR_REVIEW",
            "stop_requested": True,
            "stop_request_accepted": True,
            "stop_confirmed": True,
            "robot_stopped": True,
            "stop_stage": "MOCK_CONFIRMED",
            "stop_ack": {"ok": True, "stage": "MOCK_SKIPPED", "command_id": None},
            "runtime_robot_status": "STOPPED",
            "apply_mock_stopped": True,
        }

    ack = actuation.to_dict()
    stage = str(actuation.stage or "FAILED")
    accepted = bool(actuation.ok) and stage in {"EXECUTED", "QUEUED"}
    if stage == "EXECUTED" and actuation.ok:
        confirmed = True
        status = "PAUSED_FOR_REVIEW"
        stop_stage = "EXECUTED"
        runtime = "STOPPED"
        apply_mock = True
    elif stage == "QUEUED" and actuation.ok:
        if telemetry_confirms_stopped:
            confirmed = True
            status = "PAUSED_FOR_REVIEW"
            stop_stage = "QUEUED"
            runtime = "STOPPED"
            apply_mock = True
        else:
            confirmed = False
            status = "PAUSE_STOP_PENDING"
            stop_stage = "QUEUED"
            runtime = "STOP_UNCONFIRMED"
            apply_mock = False
    else:
        confirmed = False
        accepted = False
        status = "PAUSE_STOP_FAILED"
        stop_stage = "FAILED"
        runtime = "STOP_UNCONFIRMED"
        apply_mock = False
        if stage not in {"FAILED", "QUEUED", "EXECUTED"}:
            stop_stage = "UNVERIFIED"

    return {
        "status": status,
        "stop_requested": stop_requested,
        "stop_request_accepted": accepted,
        "stop_confirmed": confirmed,
        "robot_stopped": confirmed,
        "stop_stage": stop_stage,
        "stop_ack": ack,
        "runtime_robot_status": runtime,
        "apply_mock_stopped": apply_mock,
    }


@dataclass
class TeleopLease:
    control_id: str
    robot_id: str
    agent_id: str
    device_id: str
    credential: str
    expires_at: datetime
    max_speed: float = MAX_TELEOP_SPEED
    allowed_zones: tuple[str, ...] = ALLOWED_TELEOP_ZONES
    last_sequence: int = 0
    last_packet_at: datetime | None = None
    active: bool = True
    ai_risk: float = 0.0
    ai_model_version: str = "iforest-v1"
    created_at: datetime = field(default_factory=_utcnow)

    def expired(self, now: datetime | None = None) -> bool:
        now = now or _utcnow()
        return now >= self.expires_at or not self.active


class TeleopManager:
    def __init__(
        self,
        *,
        get_security_state: Callable[[], dict[str, Any]],
        apply_containment: Callable[[str, list[str]], None],
        append_event: Callable[[dict[str, Any]], None],
        update_mock_pose: Callable[..., None] | None = None,
        update_mock_manipulator: Callable[..., None] | None = None,
        set_runtime_state: Callable[..., None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._leases: dict[str, TeleopLease] = {}  # robot_id -> lease
        self._by_id: dict[str, TeleopLease] = {}
        self._get_security_state = get_security_state
        self._apply_containment = apply_containment
        self._append_event = append_event
        self._update_mock_pose = update_mock_pose
        self._update_mock_manipulator = update_mock_manipulator
        self._set_runtime_state = set_runtime_state
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._deadman_loop, name="teleop-deadman", daemon=True
        )
        self._thread.start()

    def reset(self) -> None:
        with self._lock:
            self._leases.clear()
            self._by_id.clear()

    def shutdown(self) -> None:
        self._stop.set()

    def config(self) -> dict[str, Any]:
        return teleop_config_payload()

    def _ai_gate(
        self,
        *,
        lease: TeleopLease,
        action_type_value: str,
        action_payload: dict[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """Score outside the teleop lock. Returns (allow, enrichment)."""
        from backend.action_context import ActionType
        from backend.ai_response import ai_engine

        decision, incident = ai_engine.evaluate_action(
            action_type=ActionType(action_type_value),
            agent_id=lease.agent_id,
            device_id=lease.device_id,
            robot_id=lease.robot_id,
            credential=lease.credential,
            session_id=lease.control_id,
            action_payload=action_payload,
            hard_reasons=[],
            protection_enabled=True,
        )
        enrichment = {
            "decision_source": decision.decision_source,
            "hard_policy_would_block": decision.hard_policy_would_block,
            "hard_policy_reasons": decision.hard_policy_reasons,
            "anomaly_risk_score": decision.anomaly_risk_score,
            "behavioral_rule_score": decision.behavioral_rule_score,
            "effective_risk": decision.effective_risk,
            "anomaly_model": decision.anomaly_model,
            "anomaly_model_version": decision.anomaly_model_version,
            "anomaly_features": decision.anomaly_features,
            "ai_mode": decision.ai_mode,
            "model_confidence": decision.model_confidence,
            "response_playbook": decision.response_playbook,
            "final_decision": decision.final_decision,
            "policy_decision": decision.policy_decision,
            "caught_by": decision.decision_source
            if decision.decision_source
            not in {"none", "deterministic_fallback"}
            else "none",
        }
        if incident:
            enrichment["incident_id"] = incident.get("incident_id")

        if decision.final_decision == "HOLD":
            # Rejected command never reaches the Isaac action adapter (caller
            # returns before maybe_actuate_*). Attempt authenticated stop, then
            # deactivate the lease. Credentials stay active.
            stop = maybe_actuate_stop(lease.robot_id)
            telemetry_stopped = self._telemetry_confirms_base_stopped(
                self._get_security_state()
            )
            classified = classify_hold_stop(
                stop, telemetry_confirms_stopped=telemetry_stopped
            )

            if classified["apply_mock_stopped"] and self._update_mock_pose is not None:
                self._update_mock_pose(
                    keep_position=True,
                    speed=0.0,
                    command_id=(stop.command_id if stop else None),
                    motion_state="STOPPED",
                )
            elif self._set_runtime_state is not None:
                # Do not invent a zero speed when Isaac stop is unconfirmed.
                self._set_runtime_state(
                    robot_status=classified["runtime_robot_status"],
                )

            if classified["apply_mock_stopped"] and self._set_runtime_state is not None:
                self._set_runtime_state(
                    robot_status=classified["runtime_robot_status"],
                    robot_speed=0.0,
                )

            with self._lock:
                lease.active = False

            enrichment["status"] = classified["status"]
            enrichment["reasons"] = [
                "AI_HOLD",
                classified["status"],
                decision.response_playbook or "SUSPICIOUS_SESSION",
            ]
            if not classified["stop_confirmed"]:
                enrichment["reasons"].append("STOP_UNCONFIRMED")
            enrichment["reasons"] = [r for r in enrichment["reasons"] if r]
            enrichment["control_id"] = lease.control_id
            enrichment["robot_id"] = lease.robot_id
            enrichment["stop_requested"] = classified["stop_requested"]
            enrichment["stop_request_accepted"] = classified["stop_request_accepted"]
            enrichment["stop_confirmed"] = classified["stop_confirmed"]
            enrichment["robot_stopped"] = classified["robot_stopped"]
            enrichment["stop_stage"] = classified["stop_stage"]
            enrichment["stop_ack"] = classified["stop_ack"]
            enrichment["credential_revoked"] = False
            enrichment["agent_quarantined"] = False

            if incident and incident.get("incident_id"):
                from backend.incident_store import incident_store

                evidence = dict(incident.get("ai_evidence") or {})
                evidence["hold_stop"] = {
                    "stop_requested": classified["stop_requested"],
                    "stop_request_accepted": classified["stop_request_accepted"],
                    "stop_confirmed": classified["stop_confirmed"],
                    "robot_stopped": classified["robot_stopped"],
                    "stop_stage": classified["stop_stage"],
                    "stop_ack": classified["stop_ack"],
                    "status": classified["status"],
                }
                incident_store.update_fields(
                    incident["incident_id"],
                    ai_evidence_json=evidence,
                )

            self._append_event(
                {
                    "timestamp": _utcnow().isoformat(),
                    "kind": "teleop_hold_pause",
                    "robot_id": lease.robot_id,
                    "control_id": lease.control_id,
                    "final_decision": "HOLD",
                    "decision_source": decision.decision_source,
                    "status": classified["status"],
                    "stop_stage": classified["stop_stage"],
                    "stop_confirmed": classified["stop_confirmed"],
                    "actions": [
                        "ROBOT_ESTOP_REQUESTED",
                        classified["status"],
                    ],
                }
            )
            return False, enrichment

        if decision.final_decision == "BLOCK":
            with self._lock:
                lease.active = False
            enrichment["status"] = "REJECTED"
            enrichment["reasons"] = [
                "AI_BLOCK",
                decision.response_playbook or "",
            ]
            enrichment["reasons"] = [r for r in enrichment["reasons"] if r]
            enrichment["control_id"] = lease.control_id
            enrichment["robot_id"] = lease.robot_id
            return False, enrichment
        return True, enrichment

    def _telemetry_confirms_base_stopped(self, security: dict[str, Any]) -> bool:
        bridge = (
            security.get("isaac_bridge_state")
            or security.get("mock_bridge_state")
            or {}
        )
        try:
            speed = float(security.get("robot_speed", bridge.get("speed", 1.0)))
        except (TypeError, ValueError):
            return False
        motion = bridge.get("motion_state") or security.get("robot_status")
        return speed == 0.0 and motion in {
            "STOPPED",
            "IDLE",
            "STOWED",
            "CONTAINED",
        }

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        credential = str(payload.get("credential", ""))
        agent_id = str(payload.get("agent_id", "fleet-agent-01"))
        device_id = str(payload.get("device_id", ""))
        robot_id = str(payload.get("robot_id", "robot-01"))
        try:
            x = _finite(payload.get("x", 0.0), "x")
            y = _finite(payload.get("y", 0.0), "y")
            speed = _finite(payload.get("speed", 0.8), "speed")
        except ValueError as exc:
            return self._hard_block(
                robot_id=robot_id,
                reasons=[str(exc)],
                agent_id=agent_id,
                device_id=device_id,
            )

        security = self._get_security_state()
        reasons = collect_reasons(
            credential=credential,
            credential_status=security.get("credential_status", "ACTIVE"),
            agent_id=agent_id,
            device_id=device_id,
            robot_id=robot_id,
            destination="SAFE_ZONE_A",  # placeholder; point check below
            speed=speed,
        )
        # Replace destination-based restriction with coordinate classification.
        reasons = [
            r
            for r in reasons
            if r
            not in {
                "RESTRICTED_DESTINATION",
                "EXCESSIVE_SPEED",
            }
        ]
        if speed > MAX_TELEOP_SPEED or speed < 0:
            reasons.append("EXCESSIVE_SPEED")
        allowed, zone = is_allowed_teleop_point(x, y)
        if not allowed:
            reasons.append("RESTRICTED_DESTINATION")

        # IsolationForest is informative only for teleop (not trained on joystick).
        risk, features, ai_info = detector.score(
            speed=speed,
            known_device=device_id == KNOWN_DEVICE,
            restricted_destination=not allowed,
            commands_last_10_seconds=1,
            previous_failures=0,
            hour_of_day=_utcnow().hour,
            seconds_since_last_command=30.0,
        )

        hard = any(r in HARD_VIOLATIONS for r in reasons) or bool(reasons)
        if hard:
            return self._hard_block(
                robot_id=robot_id,
                reasons=reasons,
                agent_id=agent_id,
                device_id=device_id,
                ai_risk=risk,
                ai_info=ai_info,
                features=features,
                zone=zone,
            )

        control_id = str(uuid.uuid4())
        expires_at = _utcnow() + timedelta(seconds=LEASE_TTL_SECONDS)
        lease = TeleopLease(
            control_id=control_id,
            robot_id=robot_id,
            agent_id=agent_id,
            device_id=device_id,
            credential=credential,
            expires_at=expires_at,
            ai_risk=risk,
            ai_model_version=str(ai_info.get("model_version", "iforest-v1")),
            last_packet_at=_utcnow(),
        )
        with self._lock:
            previous = self._leases.get(robot_id)
            if previous and previous.active and not previous.expired():
                previous.active = False
            self._leases[robot_id] = lease
            self._by_id[control_id] = lease

        event = {
            "timestamp": _utcnow().isoformat(),
            "kind": "teleop_start",
            "agent_id": agent_id,
            "device_id": device_id,
            "robot_id": robot_id,
            "final_decision": "ALLOW",
            "policy_decision": "TELEOP_LEASE_ISSUED",
            "reasons": [],
            "anomaly_risk_score": risk,
            "caught_by": "none",
            "hard_policy_would_block": False,
            "zone": zone,
            "actions": ["TELEOP_LEASE_ISSUED"],
            "ai": {
                "risk": risk,
                "model": "IsolationForest",
                "model_version": lease.ai_model_version,
                "enforcement_mode": "SHADOW_TELEOP",
                "features": features,
            },
        }
        self._append_event(event)
        return {
            "final_decision": "ALLOW",
            "policy_decision": "TELEOP_LEASE_ISSUED",
            "reasons": [],
            "control_id": control_id,
            "expires_at": expires_at.isoformat(),
            "max_speed": lease.max_speed,
            "allowed_zones": list(lease.allowed_zones),
            "zone": zone,
            "ai": {
                "risk": risk,
                "model": "IsolationForest",
                "model_version": lease.ai_model_version,
                "enforcement_mode": "SHADOW_TELEOP",
            },
        }

    def move(self, payload: dict[str, Any]) -> dict[str, Any]:
        control_id = str(payload.get("control_id", ""))
        robot_id = str(payload.get("robot_id", "robot-01"))
        try:
            sequence = int(payload.get("sequence"))
            x = _finite(payload.get("x"), "x")
            y = _finite(payload.get("y"), "y")
            speed = _finite(payload.get("speed"), "speed")
        except (TypeError, ValueError) as exc:
            return self._reject_move(
                control_id=control_id,
                robot_id=robot_id,
                reasons=[str(exc)],
                stop=True,
            )

        # Decide under the lock, act outside it. _reject_move stops the robot over
        # HTTP and appends events through the API state lock; doing either here
        # would starve _deadman_loop, which needs this lock every 100 ms.
        def _decide() -> tuple[str, dict[str, Any]]:
            """("payload", body) to return as-is, ("reject", kwargs), or ("ok", derived)."""
            with self._lock:
                lease = self._by_id.get(control_id)
                if lease is None or lease.robot_id != robot_id:
                    return (
                        "payload",
                        {
                            "status": "REJECTED",
                            "reasons": ["UNKNOWN_OR_MISMATCHED_LEASE"],
                            "control_id": control_id,
                            "sequence": sequence,
                        },
                    )
                if lease.expired():
                    lease.active = False
                    return ("reject", {"reasons": ["LEASE_EXPIRED"], "lease": lease})
                if sequence <= lease.last_sequence:
                    return (
                        "reject",
                        {
                            "reasons": ["SEQUENCE_REPLAY"],
                            "lease": lease,
                            "sequence": sequence,
                        },
                    )
                now = _utcnow()
                if lease.last_packet_at is not None:
                    # Rolling 1s window rate limit (~10 Hz with headroom).
                    recent = getattr(lease, "_packet_times", [])
                    recent = [t for t in recent if (now - t).total_seconds() < 1.0]
                    if len(recent) >= MAX_STREAM_HZ + 2:
                        return (
                            "payload",
                            {
                                "status": "REJECTED",
                                "reasons": ["RATE_LIMIT"],
                                "control_id": control_id,
                                "sequence": sequence,
                            },
                        )
                    recent.append(now)
                    lease._packet_times = recent  # type: ignore[attr-defined]
                if speed < 0 or speed > lease.max_speed:
                    return (
                        "reject",
                        {
                            "reasons": ["EXCESSIVE_SPEED"],
                            "lease": lease,
                            "sequence": sequence,
                        },
                    )
                allowed, zone = is_allowed_teleop_point(x, y)
                if not allowed or zone not in lease.allowed_zones:
                    return (
                        "reject",
                        {
                            "reasons": ["RESTRICTED_DESTINATION"],
                            "lease": lease,
                            "sequence": sequence,
                            "zone": zone,
                        },
                    )

                lease.last_sequence = sequence
                lease.last_packet_at = now
                return ("ok", {"zone": zone})

        decision = _decide()
        kind, body = decision
        if kind == "payload":
            return body
        if kind == "reject":
            return self._reject_move(
                control_id=control_id, robot_id=robot_id, stop=True, **body
            )
        # Server-derived zone: the client never supplies one.
        zone = body["zone"]

        # Security state lives behind the API state lock, so it is read with this
        # lock released -- see _validate_aux_command for why the two must never
        # be held at once. Checked before actuating, so a revoked credential
        # still stops the robot rather than moving it.
        security = self._get_security_state()
        revoked = security.get("credential_status") != "ACTIVE"
        quarantined = security.get("agent_status") == "QUARANTINED"
        if revoked or quarantined:
            with self._lock:
                lease = self._by_id.get(control_id)
                if lease is not None:
                    lease.active = False
            return self._reject_move(
                control_id=control_id,
                robot_id=robot_id,
                reasons=["REVOKED_CREDENTIAL" if revoked else "IDENTITY_QUARANTINED"],
                stop=True,
                lease=lease,
                sequence=sequence,
            )

        with self._lock:
            lease = self._by_id.get(control_id)
        if lease is None:
            return {
                "status": "REJECTED",
                "reasons": ["UNKNOWN_OR_MISMATCHED_LEASE"],
                "control_id": control_id,
                "sequence": sequence,
            }

        allow, enrich = self._ai_gate(
            lease=lease,
            action_type_value="BASE_MOVE",
            action_payload={"x": x, "y": y, "speed": speed, "zone": zone},
        )
        if not allow:
            enrich["sequence"] = sequence
            enrich["zone"] = zone
            return enrich

        actuation = maybe_actuate_move_xy(robot_id, x, y, speed)
        command_id = None
        status = "EXECUTED"
        if actuation is None:
            status = "EXECUTED"
            command_id = f"mock-{uuid.uuid4()}"
            if self._update_mock_pose:
                self._update_mock_pose(x, y, speed, command_id)
        elif not actuation.ok or actuation.stage == "FAILED":
            return {
                "status": "FAILED",
                "reasons": ["BRIDGE_FAILURE"],
                "detail": actuation.detail if actuation else None,
                "control_id": control_id,
                "sequence": sequence,
                "zone": zone,
            }
        else:
            status = actuation.stage
            command_id = actuation.command_id
            if self._update_mock_pose and actuation.stage in {"QUEUED", "EXECUTED"}:
                self._update_mock_pose(x, y, speed, command_id)

        return {
            "status": status,
            "command_id": command_id,
            "control_id": control_id,
            "sequence": sequence,
            "zone": zone,
            **{k: v for k, v in enrich.items() if k not in {"status", "reasons"}},
        }

    def arm_preset(self, payload: dict[str, Any]) -> dict[str, Any]:
        control_id = str(payload.get("control_id", ""))
        robot_id = str(payload.get("robot_id", "robot-01"))
        preset = str(payload.get("preset", "")).strip().lower()
        if preset not in ARM_PRESETS:
            return self._reject_aux_command(
                control_id=control_id,
                robot_id=robot_id,
                reasons=["INVALID_ARM_PRESET"],
                stop=False,
            )

        rejection = self._validate_aux_command(control_id, robot_id)
        if rejection is not None:
            return rejection

        with self._lock:
            lease = self._by_id.get(control_id)
        if lease is None:
            return {
                "status": "REJECTED",
                "reasons": ["UNKNOWN_OR_MISMATCHED_LEASE"],
                "control_id": control_id,
                "robot_id": robot_id,
            }
        allow, enrich = self._ai_gate(
            lease=lease,
            action_type_value="ARM_PRESET",
            action_payload={"preset": preset},
        )
        if not allow:
            return enrich

        actuation = maybe_actuate_arm_preset(robot_id, preset)
        result = self._aux_actuation_result(
            control_id=control_id,
            robot_id=robot_id,
            kind="arm_preset",
            action=f"ARM_PRESET_{preset.upper()}",
            actuation=actuation,
            extra={"preset": preset},
        )
        result.update({k: v for k, v in enrich.items() if k not in result})
        return result

    def arm_joints(self, payload: dict[str, Any]) -> dict[str, Any]:
        control_id = str(payload.get("control_id", ""))
        robot_id = str(payload.get("robot_id", "robot-01"))
        raw_targets = payload.get("targets_degrees", {})
        if not isinstance(raw_targets, dict) or not raw_targets:
            return self._reject_aux_command(
                control_id=control_id,
                robot_id=robot_id,
                reasons=["INVALID_ARM_JOINTS"],
                stop=False,
            )
        targets_degrees: dict[str, float] = {}
        try:
            for name, value in raw_targets.items():
                targets_degrees[str(name)] = _finite(value, str(name))
        except ValueError as exc:
            return self._reject_aux_command(
                control_id=control_id,
                robot_id=robot_id,
                reasons=[str(exc)],
                stop=False,
            )

        rejection = self._validate_aux_command(control_id, robot_id)
        if rejection is not None:
            return rejection

        with self._lock:
            lease = self._by_id.get(control_id)
        if lease is None:
            return {
                "status": "REJECTED",
                "reasons": ["UNKNOWN_OR_MISMATCHED_LEASE"],
                "control_id": control_id,
                "robot_id": robot_id,
            }
        allow, enrich = self._ai_gate(
            lease=lease,
            action_type_value="ARM_JOINTS",
            action_payload={"targets_degrees": targets_degrees},
        )
        if not allow:
            return enrich

        actuation = maybe_actuate_arm_joints(robot_id, targets_degrees)
        result = self._aux_actuation_result(
            control_id=control_id,
            robot_id=robot_id,
            kind="arm_joints",
            action="ARM_JOINTS",
            actuation=actuation,
            extra={"targets_degrees": targets_degrees},
        )
        result.update({k: v for k, v in enrich.items() if k not in result})
        return result

    def gripper(self, payload: dict[str, Any]) -> dict[str, Any]:
        control_id = str(payload.get("control_id", ""))
        robot_id = str(payload.get("robot_id", "robot-01"))
        action = str(payload.get("action", "")).strip().lower()
        if action not in GRIPPER_ACTIONS:
            return self._reject_aux_command(
                control_id=control_id,
                robot_id=robot_id,
                reasons=["INVALID_GRIPPER_ACTION"],
                stop=False,
            )

        rejection = self._validate_aux_command(control_id, robot_id)
        if rejection is not None:
            return rejection

        with self._lock:
            lease = self._by_id.get(control_id)
        if lease is None:
            return {
                "status": "REJECTED",
                "reasons": ["UNKNOWN_OR_MISMATCHED_LEASE"],
                "control_id": control_id,
                "robot_id": robot_id,
            }
        action_type = "GRIPPER_OPEN" if action == "open" else "GRIPPER_CLOSE"
        allow, enrich = self._ai_gate(
            lease=lease,
            action_type_value=action_type,
            action_payload={"action": action},
        )
        if not allow:
            return enrich

        actuation = maybe_actuate_gripper(robot_id, action)
        result = self._aux_actuation_result(
            control_id=control_id,
            robot_id=robot_id,
            kind="gripper",
            action=f"GRIPPER_{action.upper()}",
            actuation=actuation,
            extra={"action": action},
        )
        result.update({k: v for k, v in enrich.items() if k not in result})
        return result

    def stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        control_id = str(payload.get("control_id", ""))
        robot_id = str(payload.get("robot_id", "robot-01"))
        reason = str(payload.get("reason", "JOYSTICK_RELEASED"))
        lease_snapshot: TeleopLease | None = None
        with self._lock:
            lease = self._by_id.get(control_id)
            # Fail-safe: accept stop for a recently known lease even if expired.
            if lease is None:
                # Still attempt robot stop if any active lease on robot.
                lease = self._leases.get(robot_id)
            if lease is not None:
                lease_snapshot = lease
                lease.active = False

        # Score BASE_STOP through the unified action engine (observe mode — never
        # blocks an authenticated stop). Physical stop always proceeds.
        enrich: dict[str, Any] = {}
        if lease_snapshot is not None:
            from backend.action_context import ActionType
            from backend.ai_response import ai_engine

            decision, _incident = ai_engine.evaluate_action(
                action_type=ActionType.BASE_STOP,
                agent_id=lease_snapshot.agent_id,
                device_id=lease_snapshot.device_id,
                robot_id=lease_snapshot.robot_id,
                credential=lease_snapshot.credential,
                session_id=lease_snapshot.control_id,
                action_payload={"reason": reason},
                hard_reasons=[],
                protection_enabled=True,
            )
            enrich = {
                "decision_source": decision.decision_source,
                "anomaly_risk_score": decision.anomaly_risk_score,
                "behavioral_rule_score": decision.behavioral_rule_score,
                "effective_risk": decision.effective_risk,
                "ai_mode": decision.ai_mode,
                "final_decision": decision.final_decision,
            }

        actuation = maybe_actuate_stop(robot_id)
        if self._update_mock_pose:
            self._update_mock_pose(
                keep_position=True,
                speed=0.0,
                command_id=None,
                motion_state="STOPPED",
            )
        stage = "EXECUTED"
        command_id = None
        if actuation is not None:
            stage = actuation.stage if actuation.ok else "FAILED"
            command_id = actuation.command_id
        self._append_event(
            {
                "timestamp": _utcnow().isoformat(),
                "kind": "teleop_stop",
                "robot_id": robot_id,
                "control_id": control_id,
                "reason": reason,
                "final_decision": "STOP",
                "actions": ["TELEOP_STOP", "BASE_STOP", f"ISAAC_ESTOP_{stage}"],
                **{k: v for k, v in enrich.items() if k != "final_decision"},
            }
        )
        return {
            "status": stage,
            "command_id": command_id,
            "control_id": control_id,
            "robot_id": robot_id,
            "reason": reason,
            "action_type": "BASE_STOP",
            **enrich,
        }

    def _hard_block(
        self,
        *,
        robot_id: str,
        reasons: list[str],
        agent_id: str,
        device_id: str,
        ai_risk: float = 0.0,
        ai_info: dict[str, Any] | None = None,
        features: dict[str, Any] | None = None,
        zone: str | None = None,
    ) -> dict[str, Any]:
        actions = [
            "COMMAND_REJECTED",
            "CONTAINMENT_REQUESTED",
            "CREDENTIAL_REVOKED",
            "AGENT_QUARANTINED",
        ]
        self._apply_containment(robot_id, actions)
        maybe_actuate_stop(robot_id)
        event = {
            "timestamp": _utcnow().isoformat(),
            "kind": "teleop_start",
            "agent_id": agent_id,
            "device_id": device_id,
            "robot_id": robot_id,
            "final_decision": "BLOCK",
            "policy_decision": "DENY",
            "reasons": reasons,
            "anomaly_risk_score": ai_risk,
            "caught_by": "hard_policy",
            "hard_policy_would_block": True,
            "zone": zone,
            "actions": actions + ["ISAAC_ESTOP_QUEUED"],
            "ai": {
                "risk": ai_risk,
                "model": "IsolationForest",
                "model_version": (ai_info or {}).get("model_version", "iforest-v1"),
                "enforcement_mode": "SHADOW_TELEOP",
                "features": features or {},
            },
        }
        self._append_event(event)
        return {
            "final_decision": "BLOCK",
            "policy_decision": "DENY",
            "reasons": reasons,
            "control_id": None,
            "expires_at": None,
            "max_speed": MAX_TELEOP_SPEED,
            "allowed_zones": [],
            "zone": zone,
            "ai": {
                "risk": ai_risk,
                "model": "IsolationForest",
                "model_version": (ai_info or {}).get("model_version", "iforest-v1"),
                "enforcement_mode": "SHADOW_TELEOP",
            },
            "actions": event["actions"],
        }

    def _reject_move(
        self,
        *,
        control_id: str,
        robot_id: str,
        reasons: list[str],
        stop: bool,
        lease: TeleopLease | None = None,
        sequence: int | None = None,
        zone: str | None = None,
    ) -> dict[str, Any]:
        if stop:
            if lease is not None:
                lease.active = False
            maybe_actuate_stop(robot_id)
            # Restricted / overspeed / replay during teleop = fail closed containment
            if any(
                r in reasons
                for r in (
                    "RESTRICTED_DESTINATION",
                    "EXCESSIVE_SPEED",
                    "SEQUENCE_REPLAY",
                    "REVOKED_CREDENTIAL",
                    "IDENTITY_QUARANTINED",
                )
            ):
                self._apply_containment(
                    robot_id,
                    [
                        "COMMAND_REJECTED",
                        "CONTAINMENT_REQUESTED",
                        "CREDENTIAL_REVOKED",
                        "AGENT_QUARANTINED",
                    ],
                )
            self._append_event(
                {
                    "timestamp": _utcnow().isoformat(),
                    "kind": "teleop_move_rejected",
                    "robot_id": robot_id,
                    "control_id": control_id,
                    "reasons": reasons,
                    "final_decision": "BLOCK",
                    "zone": zone,
                }
            )
        return {
            "status": "REJECTED",
            "reasons": reasons,
            "control_id": control_id,
            "sequence": sequence,
            "zone": zone,
        }

    def _validate_aux_command(
        self, control_id: str, robot_id: str
    ) -> dict[str, Any] | None:
        """Decide under the lock, act outside it.

        _reject_aux_command talks to the Isaac bridge over HTTP and re-enters the
        API state lock, and _get_security_state re-enters it too. Holding this
        lock across either starves _deadman_loop, which needs it every 100 ms to
        honour the 750 ms deadman -- the guarantee that stops a runaway robot.
        """
        pending: tuple[list[str], bool, TeleopLease | None] | None = None

        with self._lock:
            lease = self._by_id.get(control_id)
            if lease is None or lease.robot_id != robot_id:
                pending = (["UNKNOWN_OR_MISMATCHED_LEASE"], False, None)
            elif lease.expired():
                lease.active = False
                pending = (["LEASE_EXPIRED"], True, lease)

        if pending is None:
            security = self._get_security_state()
            reason = None
            if security.get("credential_status") != "ACTIVE":
                reason = "REVOKED_CREDENTIAL"
            elif security.get("agent_status") == "QUARANTINED":
                reason = "IDENTITY_QUARANTINED"
            if reason is not None:
                with self._lock:
                    lease = self._by_id.get(control_id)
                    if lease is not None:
                        lease.active = False
                pending = ([reason], True, lease)

        if pending is None:
            return None

        reasons, stop, rejected_lease = pending
        return self._reject_aux_command(
            control_id=control_id,
            robot_id=robot_id,
            reasons=reasons,
            stop=stop,
            lease=rejected_lease,
        )

    def _reject_aux_command(
        self,
        *,
        control_id: str,
        robot_id: str,
        reasons: list[str],
        stop: bool,
        lease: TeleopLease | None = None,
    ) -> dict[str, Any]:
        if stop:
            if lease is not None:
                lease.active = False
            maybe_actuate_stop(robot_id)
            if any(r in reasons for r in ("REVOKED_CREDENTIAL", "IDENTITY_QUARANTINED")):
                self._apply_containment(
                    robot_id,
                    [
                        "COMMAND_REJECTED",
                        "CONTAINMENT_REQUESTED",
                        "CREDENTIAL_REVOKED",
                        "AGENT_QUARANTINED",
                    ],
                )
        self._append_event(
            {
                "timestamp": _utcnow().isoformat(),
                "kind": "teleop_aux_rejected",
                "robot_id": robot_id,
                "control_id": control_id,
                "reasons": reasons,
                "final_decision": "BLOCK",
            }
        )
        return {
            "status": "REJECTED",
            "reasons": reasons,
            "control_id": control_id,
            "robot_id": robot_id,
        }

    def _aux_actuation_result(
        self,
        *,
        control_id: str,
        robot_id: str,
        kind: str,
        action: str,
        actuation,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        if actuation is None:
            status = "EXECUTED"
            command_id = f"mock-{uuid.uuid4()}"
            # Mock mode has no Isaac to echo the pose back, so record it here in
            # the same shape the bridge uses.
            if self._update_mock_manipulator is not None:
                if kind == "arm_preset":
                    self._update_mock_manipulator(
                        arm={"mode": "preset", "preset": extra["preset"]},
                        last_command_id=command_id,
                    )
                elif kind == "arm_joints":
                    self._update_mock_manipulator(
                        arm={
                            "mode": "joints",
                            "targets_degrees": extra["targets_degrees"],
                        },
                        last_command_id=command_id,
                    )
                elif kind == "gripper":
                    self._update_mock_manipulator(
                        gripper={"action": extra["action"]},
                        last_command_id=command_id,
                    )
        elif not actuation.ok or actuation.stage == "FAILED":
            maybe_actuate_stop(robot_id)
            with self._lock:
                lease = self._by_id.get(control_id)
                if lease is not None:
                    lease.active = False
            return {
                "status": "FAILED",
                "reasons": ["BRIDGE_FAILURE"],
                "detail": actuation.detail if actuation else None,
                "control_id": control_id,
                "robot_id": robot_id,
                **extra,
            }
        else:
            status = actuation.stage
            command_id = actuation.command_id

        self._append_event(
            {
                "timestamp": _utcnow().isoformat(),
                "kind": f"teleop_{kind}",
                "robot_id": robot_id,
                "control_id": control_id,
                "final_decision": "ALLOW",
                "actions": [f"{action}_{status}"],
                **extra,
            }
        )
        return {
            "status": status,
            "command_id": command_id,
            "control_id": control_id,
            "robot_id": robot_id,
            **extra,
        }

    def _deadman_loop(self) -> None:
        while not self._stop.wait(0.1):
            now = _utcnow()
            to_stop: list[TeleopLease] = []
            with self._lock:
                for lease in list(self._leases.values()):
                    if not lease.active:
                        continue
                    if lease.last_packet_at is None:
                        continue
                    age_ms = (now - lease.last_packet_at).total_seconds() * 1000
                    # Only apply deadman after streaming has started (sequence > 0)
                    if lease.last_sequence > 0 and age_ms > DEADMAN_TIMEOUT_MS:
                        lease.active = False
                        to_stop.append(lease)
            for lease in to_stop:
                maybe_actuate_stop(lease.robot_id)
                self._append_event(
                    {
                        "timestamp": _utcnow().isoformat(),
                        "kind": "teleop_deadman",
                        "robot_id": lease.robot_id,
                        "control_id": lease.control_id,
                        "final_decision": "STOP",
                        "actions": ["TELEOP_DEADMAN_STOP"],
                        "reasons": ["TELEOP_DEADMAN_STOP"],
                    }
                )
