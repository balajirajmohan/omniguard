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

from backend.actuation import maybe_actuate_move_xy, maybe_actuate_stop
from backend.anomaly import detector
from backend.policy import HARD_VIOLATIONS, KNOWN_DEVICE, collect_reasons
from backend.zones import (
    ALLOWED_TELEOP_ZONES,
    MAX_TELEOP_SPEED,
    is_allowed_teleop_point,
    teleop_config_payload,
)

LEASE_TTL_SECONDS = 30
DEADMAN_TIMEOUT_MS = int(os.getenv("TELEOP_DEADMAN_TIMEOUT_MS", "750"))
MAX_STREAM_HZ = 10
MIN_PACKET_INTERVAL_S = 1.0 / MAX_STREAM_HZ


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


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
        update_mock_pose: Callable[[float, float, float, str | None], None] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._leases: dict[str, TeleopLease] = {}  # robot_id -> lease
        self._by_id: dict[str, TeleopLease] = {}
        self._get_security_state = get_security_state
        self._apply_containment = apply_containment
        self._append_event = append_event
        self._update_mock_pose = update_mock_pose
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

        with self._lock:
            lease = self._by_id.get(control_id)
            if lease is None or lease.robot_id != robot_id:
                return {
                    "status": "REJECTED",
                    "reasons": ["UNKNOWN_OR_MISMATCHED_LEASE"],
                    "control_id": control_id,
                    "sequence": sequence,
                }
            if lease.expired():
                lease.active = False
                return self._reject_move(
                    control_id=control_id,
                    robot_id=robot_id,
                    reasons=["LEASE_EXPIRED"],
                    stop=True,
                    lease=lease,
                )

            security = self._get_security_state()
            if security.get("credential_status") != "ACTIVE":
                lease.active = False
                return self._reject_move(
                    control_id=control_id,
                    robot_id=robot_id,
                    reasons=["REVOKED_CREDENTIAL"],
                    stop=True,
                    lease=lease,
                )
            if security.get("agent_status") == "QUARANTINED":
                lease.active = False
                return self._reject_move(
                    control_id=control_id,
                    robot_id=robot_id,
                    reasons=["IDENTITY_QUARANTINED"],
                    stop=True,
                    lease=lease,
                )
            if sequence <= lease.last_sequence:
                return self._reject_move(
                    control_id=control_id,
                    robot_id=robot_id,
                    reasons=["SEQUENCE_REPLAY"],
                    stop=True,
                    lease=lease,
                    sequence=sequence,
                )
            now = _utcnow()
            if lease.last_packet_at is not None:
                # Rolling 1s window rate limit (~10 Hz with headroom).
                recent = getattr(lease, "_packet_times", [])
                recent = [t for t in recent if (now - t).total_seconds() < 1.0]
                if len(recent) >= MAX_STREAM_HZ + 2:
                    return {
                        "status": "REJECTED",
                        "reasons": ["RATE_LIMIT"],
                        "control_id": control_id,
                        "sequence": sequence,
                    }
                recent.append(now)
                lease._packet_times = recent  # type: ignore[attr-defined]
            if speed < 0 or speed > lease.max_speed:
                return self._reject_move(
                    control_id=control_id,
                    robot_id=robot_id,
                    reasons=["EXCESSIVE_SPEED"],
                    stop=True,
                    lease=lease,
                    sequence=sequence,
                )
            allowed, zone = is_allowed_teleop_point(x, y)
            if not allowed or zone not in lease.allowed_zones:
                return self._reject_move(
                    control_id=control_id,
                    robot_id=robot_id,
                    reasons=["RESTRICTED_DESTINATION"],
                    stop=True,
                    lease=lease,
                    sequence=sequence,
                    zone=zone,
                )

            lease.last_sequence = sequence
            lease.last_packet_at = now

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
        }

    def stop(self, payload: dict[str, Any]) -> dict[str, Any]:
        control_id = str(payload.get("control_id", ""))
        robot_id = str(payload.get("robot_id", "robot-01"))
        reason = str(payload.get("reason", "JOYSTICK_RELEASED"))
        with self._lock:
            lease = self._by_id.get(control_id)
            # Fail-safe: accept stop for a recently known lease even if expired.
            if lease is None:
                # Still attempt robot stop if any active lease on robot.
                lease = self._leases.get(robot_id)
            if lease is not None:
                lease.active = False
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
                "actions": ["TELEOP_STOP", f"ISAAC_ESTOP_{stage}"],
            }
        )
        return {
            "status": stage,
            "command_id": command_id,
            "control_id": control_id,
            "robot_id": robot_id,
            "reason": reason,
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
