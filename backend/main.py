from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()

from backend.actuation import fetch_bridge_state, maybe_actuate_move, maybe_actuate_stop
from backend.agent import InvestigationAgent
from backend.anomaly import detector
from backend.behavior import BehaviorContext, behavior_tracker
from backend.incident_ai import explain_incident, llm_status
from backend.policy import (
    AI_ENFORCE,
    HARD_VIOLATIONS,
    KNOWN_DEVICE,
    RESTRICTED_ZONE,
    SAFE_ZONES,
    VALID_TOKEN,
    collect_reasons,
    decide,
)
from backend.scenarios import get_scenario, list_scenarios
from backend.teleop import TeleopManager

SIMULATOR_TOKEN = os.getenv("OMNIGUARD_SIMULATOR_TOKEN", "omniguard-sim")
OPERATOR_TOKEN = os.getenv("OMNIGUARD_OPERATOR_TOKEN", "omniguard-operator")

app = FastAPI(
    title="OmniGuard API",
    version="0.3.0",
    description=(
        "LOCAL DEMO broker for the hackathon path. "
        "Demo credential is a shared secret (OMNIGUARD_DEMO_TOKEN), not a signed JWT. "
        "Do not expose on the public internet."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_LOCK = threading.RLock()


def initial_state() -> dict[str, Any]:
    return {
        "protection_enabled": True,
        "credential_status": "ACTIVE",
        "agent_status": "TRUSTED",
        "robot_status": "STOPPED",
        "robot_zone": "SAFE_ZONE_A",
        "robot_speed": 0.0,
        "demo_run_id": str(uuid.uuid4()),
        "events": [],
        "command_queue": [{"action": "RESET"}],
        "last_containment_ack": None,
        "last_command_at": None,
        "timeline": [],
        "mock_bridge_state": {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "target": None,
            "speed": 0.0,
            "motion_state": "IDLE",
            "last_command_id": None,
        },
        "active_teleop": None,
    }


STATE = initial_state()


class CommandRequest(BaseModel):
    """Public command properties only. Protection is always enforced server-side."""

    model_config = ConfigDict(extra="forbid")

    credential: str
    agent_id: str = "fleet-agent-01"
    device_id: str
    robot_id: str = "robot-01"
    destination: str
    speed: float = Field(ge=0, le=10)


class TeleopStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential: str
    agent_id: str = "fleet-agent-01"
    device_id: str
    robot_id: str = "robot-01"
    x: float = 0.0
    y: float = 0.0
    speed: float = 0.8


class TeleopMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_id: str
    sequence: int = Field(ge=1)
    robot_id: str = "robot-01"
    x: float
    y: float
    speed: float


class TeleopStopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_id: str
    robot_id: str = "robot-01"
    reason: str = "JOYSTICK_RELEASED"


class TeleopArmPresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_id: str
    robot_id: str = "robot-01"
    preset: str


class TeleopArmJointsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_id: str
    robot_id: str = "robot-01"
    targets_degrees: dict[str, float]


class TeleopGripperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_id: str
    robot_id: str = "robot-01"
    action: str


class Telemetry(BaseModel):
    status: str
    zone: str
    speed: float | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_simulator(x_omniguard_simulator: str | None = Header(default=None)) -> None:
    if x_omniguard_simulator != SIMULATOR_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Simulator channel requires X-OmniGuard-Simulator header",
        )


def require_operator_for_protection_off(
    protection: bool,
    x_omniguard_operator: str | None,
) -> None:
    if protection:
        return
    if x_omniguard_operator != OPERATOR_TOKEN:
        raise HTTPException(
            status_code=401,
            detail=(
                "Disabling protection requires X-OmniGuard-Operator header "
                "(demo comparison only)"
            ),
        )


def _security_snapshot() -> dict[str, Any]:
    with _LOCK:
        return {
            "credential_status": STATE["credential_status"],
            "agent_status": STATE["agent_status"],
            "robot_status": STATE["robot_status"],
            "robot_speed": STATE["robot_speed"],
            "demo_run_id": STATE.get("demo_run_id"),
            "isaac_bridge_state": STATE.get("isaac_bridge_state"),
            "mock_bridge_state": STATE.get("mock_bridge_state"),
        }


def _set_runtime_state(**fields: Any) -> None:
    """Update selected runtime fields without inventing motion confirmation."""
    allowed = {
        "robot_status",
        "robot_speed",
        "credential_status",
        "agent_status",
        "last_containment_ack",
    }
    with _LOCK:
        for key, value in fields.items():
            if key in allowed:
                STATE[key] = value


def _apply_containment(robot_id: str, actions: list[str]) -> None:
    with _LOCK:
        STATE["credential_status"] = "REVOKED"
        STATE["agent_status"] = "QUARANTINED"
        STATE["robot_status"] = "CONTAINED"
        STATE["robot_speed"] = 0.0
        STATE["last_containment_ack"] = "CONTAINMENT_REQUESTED"
        STATE["command_queue"].clear()
        STATE["command_queue"].append({"action": "STOP"})
        STATE["active_teleop"] = None


def _append_teleop_event(event: dict[str, Any]) -> None:
    with _LOCK:
        STATE["events"].insert(0, event)
        STATE["events"] = STATE["events"][:100]
        STATE["timeline"].insert(
            0,
            {
                "at": event.get("timestamp", now()),
                "step": event.get("kind", "teleop"),
                "detail": {
                    "final_decision": event.get("final_decision"),
                    "reasons": event.get("reasons"),
                    "actions": event.get("actions"),
                },
            },
        )
        STATE["timeline"] = STATE["timeline"][:200]


def _update_mock_pose(
    x: float = 0.0,
    y: float = 0.0,
    speed: float = 0.0,
    command_id: str | None = None,
    motion_state: str | None = None,
    *,
    keep_position: bool = False,
) -> None:
    with _LOCK:
        bridge = STATE["mock_bridge_state"]
        if motion_state == "STOPPED":
            bridge["speed"] = 0.0
            bridge["motion_state"] = "STOPPED"
            bridge["target"] = None
            STATE["robot_speed"] = 0.0
            if STATE["robot_status"] not in {"CONTAINED", "CONTAINMENT_FAILED"}:
                STATE["robot_status"] = "STOPPED"
            if command_id:
                bridge["last_command_id"] = command_id
            return
        if not keep_position:
            bridge["position"] = {"x": float(x), "y": float(y), "z": 0.0}
            bridge["target"] = {"x": float(x), "y": float(y)}
        bridge["speed"] = float(speed)
        bridge["motion_state"] = "MOVING" if speed > 0 else "IDLE"
        if command_id:
            bridge["last_command_id"] = command_id
        STATE["robot_speed"] = float(speed)
        if speed > 0 and STATE["robot_status"] not in {"CONTAINED", "CONTAINMENT_FAILED"}:
            STATE["robot_status"] = "MOVING"


def _update_mock_manipulator(**fields: Any) -> None:
    """Mirror an executed arm/gripper command into the mock bridge state.

    The real bridge grows `arm` / `gripper` keys only once Isaac executes a
    command (isaac/warehouse_robot_demo.py -> mark_executed). Without this the
    mock path never reports them at all, so /api/state could never show arm or
    gripper state when OMNIGUARD_ROBOT_BACKEND is not "isaac".
    """
    with _LOCK:
        STATE["mock_bridge_state"].update(fields)


teleop_manager = TeleopManager(
    get_security_state=_security_snapshot,
    apply_containment=_apply_containment,
    append_event=_append_teleop_event,
    update_mock_pose=_update_mock_pose,
    update_mock_manipulator=_update_mock_manipulator,
    set_runtime_state=_set_runtime_state,
)

from backend.action_history import action_history
from backend.ai_response import ai_engine
from backend.incident_store import FEEDBACK, incident_store
from backend.investigation_service import investigation_service
from backend.incident_service import record_security_decision
from backend.recovery import recovery_manager
from backend.risk_policy import risk_policy
from backend.action_anomaly import action_window_detector


def reset_state() -> dict[str, Any]:
    # Drop teleop leases first, and outside _LOCK. TeleopManager takes its own
    # lock, and its callbacks (_append_teleop_event, _apply_containment,
    # _security_snapshot, _update_mock_pose) re-enter _LOCK. Holding _LOCK while
    # calling into the manager is therefore the reverse of the order every other
    # path uses, and two concurrent requests can deadlock the whole API.
    teleop_manager.reset()
    action_history.reset_demo_state()
    # Durable incidents are preserved across Reset Demo so investigation evidence
    # survives a judge demo cycle. Use an explicit purge endpoint/operator action
    # if wiping the SQLite store is required.
    with _LOCK:
        STATE.clear()
        STATE.update(initial_state())
        behavior_tracker.reset()
        return public_state_unlocked()


def public_state_unlocked() -> dict[str, Any]:
    return {key: value for key, value in STATE.items() if key != "command_queue"}


def public_state() -> dict[str, Any]:
    with _LOCK:
        return public_state_unlocked()


ai_engine.bind(
    state_provider=public_state,
    apply_identity_containment=_apply_containment,
    terminate_session=lambda _robot_id: teleop_manager.reset(),
)
investigation_service.bind(public_state)


def _append_timeline(steps: list[dict[str, Any]]) -> None:
    for step in steps:
        STATE["timeline"].insert(0, step)
    STATE["timeline"] = STATE["timeline"][:200]


def _classify_caught_by(
    *,
    hard_policy_would_block: bool,
    decision: str,
    policy_decision: str,
) -> str:
    if hard_policy_would_block and decision == "BLOCK":
        return "hard_policy"
    if decision == "BLOCK" and not hard_policy_would_block:
        return "ai_anomaly"
    if decision == "HOLD":
        return "ai_warning"
    if policy_decision == "AI_SHADOW_ALERT":
        return "ai_shadow"
    return "none"


def _scenario_behavior(scenario: dict[str, Any]) -> BehaviorContext | None:
    keys = (
        "commands_last_10_seconds",
        "previous_failures",
        "hour_of_day",
        "seconds_since_last_command",
    )
    if not any(k in scenario for k in keys):
        return None
    return BehaviorContext(
        commands_last_10_seconds=int(scenario.get("commands_last_10_seconds", 1)),
        previous_failures=int(scenario.get("previous_failures", 0)),
        hour_of_day=int(scenario.get("hour_of_day", 12)),
        seconds_since_last_command=float(
            scenario.get("seconds_since_last_command", 30.0)
        ),
        source="scenario",
    )


def evaluate(
    command: CommandRequest,
    *,
    protection_enabled: bool = True,
    behavior_override: BehaviorContext | None = None,
) -> dict[str, Any]:
    """Decide + contain without holding `_LOCK` during Isaac or Sonnet I/O."""
    # --- short lock: immutable snapshot ---
    with _LOCK:
        snap = {
            "credential_status": STATE["credential_status"],
            "demo_run_id": STATE["demo_run_id"],
            "agent_status": STATE["agent_status"],
        }
        STATE["protection_enabled"] = protection_enabled

    known_device = command.device_id == KNOWN_DEVICE
    restricted = command.destination not in SAFE_ZONES
    now_dt = datetime.now(timezone.utc)

    behavior = behavior_tracker.snapshot(
        agent_id=command.agent_id,
        device_id=command.device_id,
        now=now_dt,
        override=behavior_override,
    )

    timeline_steps = [
        {
            "at": now(),
            "step": "command_received",
            "detail": {
                "destination": command.destination,
                "speed": command.speed,
                "device_id": command.device_id,
            },
        }
    ]

    # --- outside lock: local ML + policy ---
    risk, features, ai_info = detector.score(
        speed=command.speed,
        known_device=known_device,
        restricted_destination=restricted,
        commands_last_10_seconds=behavior.commands_last_10_seconds,
        previous_failures=behavior.previous_failures,
        hour_of_day=behavior.hour_of_day,
        seconds_since_last_command=behavior.seconds_since_last_command,
    )
    timeline_steps.append(
        {
            "at": now(),
            "step": "behavioral_features_calculated",
            "detail": behavior.to_dict(),
        }
    )
    timeline_steps.append(
        {
            "at": now(),
            "step": "risk_scored",
            "detail": {"risk": risk, "model": ai_info.get("model_version")},
        }
    )

    reasons = collect_reasons(
        credential=command.credential,
        credential_status=snap["credential_status"],
        agent_id=command.agent_id,
        device_id=command.device_id,
        robot_id=command.robot_id,
        destination=command.destination,
        speed=command.speed,
    )
    hard_policy_would_block = any(r in HARD_VIOLATIONS for r in reasons)
    timeline_steps.append(
        {
            "at": now(),
            "step": "identity_verified",
            "detail": {
                "credential_valid": command.credential == VALID_TOKEN,
                "reasons": reasons,
                "hard_policy_would_block": hard_policy_would_block,
            },
        }
    )

    outcome = decide(
        protection_enabled=protection_enabled,
        reasons=reasons,
        risk=risk,
    )
    decision = outcome["final_decision"]
    actions = list(outcome["actions"])
    timeline_steps.append(
        {
            "at": now(),
            "step": "policy_decision",
            "detail": {
                "final_decision": decision,
                "policy_decision": outcome["policy_decision"],
            },
        }
    )

    if decision in {"BLOCK", "HOLD"} or hard_policy_would_block:
        behavior_tracker.record_failure(command.agent_id, command.device_id)

    # --- short lock: apply in-memory security/robot state (no network) ---
    with _LOCK:
        if decision == "ALLOW":
            STATE["command_queue"].append(
                {
                    "action": "MOVE",
                    "destination": command.destination,
                    "speed": command.speed,
                }
            )
            STATE["robot_speed"] = command.speed
            STATE["robot_status"] = "MOVING"
        elif outcome["contain"]:
            STATE["command_queue"].clear()
            STATE["command_queue"].append({"action": "STOP"})
            STATE["robot_status"] = "CONTAINED"
            STATE["robot_speed"] = 0.0
            STATE["credential_status"] = "REVOKED"
            STATE["agent_status"] = "QUARANTINED"
            STATE["last_containment_ack"] = "CONTAINMENT_REQUESTED"
            timeline_steps.append(
                {
                    "at": now(),
                    "step": "containment_requested",
                    "detail": {"actions": list(actions)},
                }
            )

    # --- outside lock: Isaac bridge I/O ---
    actuation = None
    if decision == "ALLOW":
        actuation = maybe_actuate_move(
            command.robot_id, command.destination, command.speed
        )
    elif outcome["contain"]:
        actuation = maybe_actuate_stop(command.robot_id)

    containment_payload: dict[str, Any] | None = None
    with _LOCK:
        if decision == "ALLOW":
            if actuation is None:
                pass
            elif not actuation.ok or actuation.stage == "FAILED":
                actions.append("ISAAC_ACTUATION_FAILED")
                STATE["robot_status"] = "MOVE_FAILED"
                timeline_steps.append(
                    {
                        "at": now(),
                        "step": "isaac_acknowledgement",
                        "detail": actuation.to_dict(),
                    }
                )
            else:
                actions.append(f"ISAAC_MOVE_{actuation.stage}")
                STATE["robot_zone"] = command.destination
                STATE["robot_status"] = "MOVING"
                timeline_steps.append(
                    {
                        "at": now(),
                        "step": "isaac_acknowledgement",
                        "detail": actuation.to_dict(),
                    }
                )
        elif outcome["contain"]:
            if actuation is None:
                actions.append("STOP_QUEUED_FOR_SIMULATOR")
                STATE["last_containment_ack"] = "STOP_QUEUED"
                containment_payload = {
                    "ok": True,
                    "acknowledged": ["ROBOT_ESTOP_REQUESTED", "STOP_BASE"],
                    "stage": "MOCK_SKIPPED",
                }
            elif actuation.stage == "FAILED" or not actuation.ok:
                actions.append("ISAAC_ESTOP_FAILED")
                STATE["robot_status"] = "CONTAINMENT_FAILED"
                STATE["last_containment_ack"] = "ESTOP_FAILED"
                containment_payload = {
                    "ok": False,
                    "failed": ["ROBOT_ESTOP_REQUESTED", "STOP_BASE"],
                    "stage": "FAILED",
                    "bridge": actuation.to_dict(),
                }
                timeline_steps.append(
                    {
                        "at": now(),
                        "step": "isaac_acknowledgement",
                        "detail": actuation.to_dict(),
                    }
                )
            elif actuation.stage == "EXECUTED":
                actions.append("ISAAC_ESTOP_EXECUTED")
                actions.append("ROBOT_STOPPED")
                STATE["last_containment_ack"] = "ESTOP_EXECUTED"
                containment_payload = {
                    "ok": True,
                    "acknowledged": ["ROBOT_ESTOP_REQUESTED", "STOP_BASE"],
                    "stage": "EXECUTED",
                    "bridge": actuation.to_dict(),
                }
                timeline_steps.append(
                    {
                        "at": now(),
                        "step": "isaac_acknowledgement",
                        "detail": actuation.to_dict(),
                    }
                )
            else:
                actions.append("ISAAC_ESTOP_QUEUED")
                STATE["last_containment_ack"] = "ESTOP_QUEUED"
                containment_payload = {
                    "ok": True,
                    "acknowledged": ["ROBOT_ESTOP_REQUESTED"],
                    "unverified": ["STOP_BASE"],
                    "stage": "QUEUED",
                    "bridge": actuation.to_dict(),
                }
                timeline_steps.append(
                    {
                        "at": now(),
                        "step": "isaac_acknowledgement",
                        "detail": actuation.to_dict(),
                    }
                )

        caught_by = _classify_caught_by(
            hard_policy_would_block=hard_policy_would_block,
            decision=decision,
            policy_decision=outcome["policy_decision"],
        )
        if hard_policy_would_block:
            decision_source = "hard_policy"
        elif caught_by == "ai_anomaly":
            decision_source = "command_anomaly_ai"
        elif caught_by == "ai_warning":
            decision_source = "ai_warning"
        else:
            decision_source = caught_by if caught_by != "none" else "none"

        event: dict[str, Any] = {
            "timestamp": now(),
            "agent_id": command.agent_id,
            "device_id": command.device_id,
            "robot_id": command.robot_id,
            "destination": command.destination,
            "speed": command.speed,
            "credential_valid": command.credential == VALID_TOKEN,
            "policy_decision": outcome["policy_decision"],
            "hard_policy_would_block": hard_policy_would_block,
            "behavior": behavior.to_dict(),
            "anomaly_model": ai_info.get("model_name", "IsolationForest"),
            "anomaly_model_version": ai_info.get("model_version"),
            "anomaly_risk_score": risk,
            "ai_anomalous": ai_info.get("ai_anomalous", False),
            "ai_unavailable": ai_info.get("ai_unavailable", False),
            "anomaly_features": features,
            "anomaly_info": ai_info,
            "final_decision": decision,
            "reasons": reasons,
            "actions": actions,
            "containment_actions": actions if outcome["contain"] else [],
            "caught_by": caught_by,
            "decision_source": decision_source,
            "timeline": list(reversed(timeline_steps)),
            "protection_enabled": protection_enabled,
            "investigation_status": None,
            "incident_id": None,
        }
        if containment_payload is not None:
            event["containment"] = containment_payload
        _append_timeline(timeline_steps)
        STATE["last_command_at"] = event["timestamp"]
        STATE["events"].insert(0, event)
        STATE["events"] = STATE["events"][:100]
        # Return a copy so later durable-incident enrichment is not raced.
        response = dict(event)

    # --- outside lock: durable incident + async Sonnet ---
    if decision in {"BLOCK", "HOLD"}:
        playbook = None
        if hard_policy_would_block:
            from backend.incident_classification import playbook_for_hard_reasons

            playbook = playbook_for_hard_reasons(reasons)
        elif decision == "BLOCK":
            playbook = "CRITICAL_PHYSICAL_RISK"
        else:
            playbook = "SUSPICIOUS_SESSION"

        enrichment = record_security_decision(
            {
                "final_decision": decision,
                "decision_source": decision_source,
                "reasons": reasons,
                "hard_policy_would_block": hard_policy_would_block,
                "requires_incident": True,
                "requires_human_review": decision == "HOLD",
                "agent_id": command.agent_id,
                "device_id": command.device_id,
                "robot_id": command.robot_id,
                "destination": command.destination,
                "speed": command.speed,
                "policy_decision": outcome["policy_decision"],
                "response_playbook": playbook,
                "anomaly_risk_score": risk,
                "anomaly_features": features,
                "anomaly_model_version": ai_info.get("model_version"),
                "ai_evidence": {
                    "anomaly_risk_score": risk,
                    "thresholds": {"warning": 0.60, "critical": 0.80},
                    "artifact_verified": ai_info.get("artifact_verified"),
                    "enforcement": "enforce" if AI_ENFORCE else "shadow",
                    "model_name": ai_info.get("model_name"),
                },
            },
            credential=command.credential,
            demo_run_id=snap["demo_run_id"],
            schedule_investigation=decision == "BLOCK",
            contain=outcome["contain"],
            containment_result=containment_payload,
        )
        response["incident_id"] = enrichment.get("incident_id")
        response["investigation_status"] = enrichment.get("investigation_status")
        response["decision_source"] = enrichment.get("decision_source") or decision_source
        response["response_playbook"] = enrichment.get("response_playbook")
        if containment_payload is not None:
            response["containment"] = containment_payload
        # Keep in-memory event aligned (best-effort; no long lock).
        with _LOCK:
            if STATE["events"] and STATE["events"][0].get("timestamp") == response.get(
                "timestamp"
            ):
                STATE["events"][0]["incident_id"] = response.get("incident_id")
                STATE["events"][0]["investigation_status"] = response.get(
                    "investigation_status"
                )

    return response


@app.get("/health")
def health() -> dict[str, Any]:
    anomaly = detector.status()
    action_ai = action_window_detector.status()
    return {
        "status": "ok",
        "service": "omniguard",
        "mode": "local-demo",
        "robot_backend": os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock"),
        "isaac_bridge_url": os.getenv("ISAAC_BRIDGE_URL", "http://127.0.0.1:8899"),
        "llm": llm_status(),
        "anomaly": anomaly,
        "action_window_anomaly": action_ai,
        "risk_policy": risk_policy.status(),
        "ai_enforcement_enabled": AI_ENFORCE,
        "model_available": anomaly.get("available", False),
        "model_degraded": anomaly.get("degraded", False),
        "artifact_verified": anomaly.get("artifact_verified", False),
        "critical_threshold": anomaly.get("critical_threshold"),
        "warning_threshold": anomaly.get("warning_threshold"),
    }


@app.get("/api/scenarios")
def scenarios() -> list[dict[str, Any]]:
    return list_scenarios()


@app.post("/api/scenarios/{scenario_id}/run")
def run_scenario(
    scenario_id: str,
    protection: bool = Query(default=True),
    reset_first: bool = Query(default=True),
    x_omniguard_operator: str | None = Header(default=None),
) -> dict[str, Any]:
    require_operator_for_protection_off(protection, x_omniguard_operator)
    if scenario_id == "valid_identity_malicious_manipulation":
        return _run_malicious_manipulation_scenario()
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}")

    if reset_first and not scenario.get("requires_prior_revoke"):
        reset_state()
    elif scenario.get("requires_prior_revoke"):
        with _LOCK:
            already_revoked = STATE["credential_status"] == "REVOKED"
        if not already_revoked:
            reset_state()
            evaluate(
                CommandRequest(
                    credential=VALID_TOKEN,
                    device_id="unknown-attacker-device",
                    destination=RESTRICTED_ZONE,
                    speed=3.5,
                ),
                protection_enabled=True,
                behavior_override=BehaviorContext(
                    commands_last_10_seconds=8,
                    previous_failures=3,
                    hour_of_day=12,
                    seconds_since_last_command=2.0,
                    source="scenario",
                ),
            )

    return evaluate(
        CommandRequest(
            credential=scenario["credential"],
            agent_id=scenario["agent_id"],
            device_id=scenario["device_id"],
            robot_id=scenario["robot_id"],
            destination=scenario["destination"],
            speed=scenario["speed"],
        ),
        protection_enabled=protection,
        behavior_override=_scenario_behavior(scenario),
    )


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    return reset_state()


@app.post("/api/commands")
def commands(command: CommandRequest) -> dict[str, Any]:
    # Public path always enforces protection — no caller override.
    return evaluate(command, protection_enabled=True)


@app.post("/api/demo/normal")
def demo_normal() -> dict[str, Any]:
    reset_state()
    return evaluate(
        CommandRequest(
            credential=VALID_TOKEN,
            device_id=KNOWN_DEVICE,
            destination="SAFE_ZONE_B",
            speed=0.8,
        ),
        protection_enabled=True,
        behavior_override=BehaviorContext(
            commands_last_10_seconds=1,
            previous_failures=0,
            hour_of_day=10,
            seconds_since_last_command=40.0,
            source="scenario",
        ),
    )


@app.post("/api/demo/attack")
def demo_attack(
    protection: bool = Query(default=True),
    x_omniguard_operator: str | None = Header(default=None),
) -> dict[str, Any]:
    require_operator_for_protection_off(protection, x_omniguard_operator)
    reset_state()
    return evaluate(
        CommandRequest(
            credential=VALID_TOKEN,
            device_id="unknown-attacker-device",
            destination=RESTRICTED_ZONE,
            speed=3.5,
        ),
        protection_enabled=protection,
        behavior_override=BehaviorContext(
            commands_last_10_seconds=8,
            previous_failures=3,
            hour_of_day=12,
            seconds_since_last_command=2.0,
            source="scenario",
        ),
    )


@app.post("/api/demo/anomaly")
def demo_anomaly() -> dict[str, Any]:
    """Rule-passing command that IsolationForest should block (unknown threat)."""
    reset_state()
    return evaluate(
        CommandRequest(
            credential=VALID_TOKEN,
            device_id=KNOWN_DEVICE,
            destination="SAFE_ZONE_B",
            speed=1.45,
        ),
        protection_enabled=True,
        behavior_override=BehaviorContext(
            commands_last_10_seconds=10,
            previous_failures=4,
            hour_of_day=3,
            seconds_since_last_command=1.5,
            source="scenario",
        ),
    )


@app.get("/api/teleop/config")
def teleop_config() -> dict[str, Any]:
    return teleop_manager.config()


@app.post("/api/teleop/start")
def teleop_start(body: TeleopStartRequest) -> dict[str, Any]:
    result = teleop_manager.start(body.model_dump())
    with _LOCK:
        STATE["active_teleop"] = {
            "control_id": result.get("control_id"),
            "decision": result.get("final_decision"),
            "ai": result.get("ai"),
        }
    return result


@app.post("/api/teleop/move")
def teleop_move(body: TeleopMoveRequest) -> dict[str, Any]:
    return teleop_manager.move(body.model_dump())


@app.post("/api/teleop/arm/preset")
def teleop_arm_preset(body: TeleopArmPresetRequest) -> dict[str, Any]:
    return teleop_manager.arm_preset(body.model_dump())


@app.post("/api/teleop/arm/joints")
def teleop_arm_joints(body: TeleopArmJointsRequest) -> dict[str, Any]:
    return teleop_manager.arm_joints(body.model_dump())


@app.post("/api/teleop/gripper")
def teleop_gripper(body: TeleopGripperRequest) -> dict[str, Any]:
    return teleop_manager.gripper(body.model_dump())


@app.post("/api/teleop/stop")
def teleop_stop(body: TeleopStopRequest) -> dict[str, Any]:
    result = teleop_manager.stop(body.model_dump())
    with _LOCK:
        STATE["active_teleop"] = None
        STATE["robot_speed"] = 0.0
        if STATE["robot_status"] not in {"CONTAINED", "CONTAINMENT_FAILED"}:
            STATE["robot_status"] = "STOPPED"
    return result


@app.get("/api/state")
def state() -> dict[str, Any]:
    payload = public_state()
    bridge = fetch_bridge_state()
    if bridge is not None:
        payload["isaac_bridge_state"] = bridge
    else:
        payload["isaac_bridge_state"] = payload.get("mock_bridge_state")
    return payload


@app.get("/api/events")
def events() -> list[dict[str, Any]]:
    with _LOCK:
        return list(STATE["events"])


@app.get("/api/timeline")
def timeline() -> list[dict[str, Any]]:
    with _LOCK:
        return list(STATE["timeline"])


@app.post("/api/investigate")
def investigate() -> dict[str, Any]:
    agent = InvestigationAgent(public_state)
    result = agent.run()
    with _LOCK:
        STATE["timeline"].insert(
            0,
            {
                "at": now(),
                "step": "investigation_agent",
                "detail": {
                    "tools_used": result.get("tools_used"),
                    "disallowed": result.get("disallowed"),
                },
            },
        )
        STATE["timeline"] = STATE["timeline"][:200]
    return result


class IncidentFeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: str
    notes: str | None = None


class RecoveryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: dict[str, bool] = Field(default_factory=dict)
    force_state: str | None = None


@app.get("/api/ai/status")
def ai_status() -> dict[str, Any]:
    return {
        "command_anomaly": detector.status(),
        "action_window_anomaly": action_window_detector.status(),
        "risk_policy": risk_policy.status(),
        "llm": llm_status(),
        "note": (
            "anomaly_risk_score is an IsolationForest anomaly score, not an "
            "attack probability. model_confidence is null unless calibrated."
        ),
    }


@app.get("/api/incidents")
def list_incidents(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return incident_store.list(limit=limit)


@app.get("/api/incidents/latest")
def latest_incident() -> dict[str, Any]:
    durable = incident_store.list(limit=1)
    with _LOCK:
        for event in STATE["events"]:
            if event.get("final_decision") == "BLOCK":
                return {
                    "incident": event,
                    "durable_incident": durable[0] if durable else None,
                    "exported_at": now(),
                }
        return {
            "incident": None,
            "durable_incident": durable[0] if durable else None,
            "exported_at": now(),
        }


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict[str, Any]:
    incident = incident_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.post("/api/incidents/{incident_id}/investigate")
def investigate_incident(
    incident_id: str,
    x_omniguard_operator: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_omniguard_operator != OPERATOR_TOKEN:
        raise HTTPException(status_code=401, detail="Operator authorization required")
    incident = incident_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    result = investigation_service.schedule(incident_id, force=True)
    # Wait briefly is not required — return pending/completed snapshot.
    refreshed = incident_store.get(incident_id) or incident
    explanation = refreshed.get("llm_explanation")
    return {
        "incident_id": incident_id,
        "investigation": refreshed.get("agent_trace"),
        "explanation": explanation,
        "ok": result.get("ok", True),
        "investigation_status": result.get("investigation_status")
        or (explanation or {}).get("investigation_status")
        or (explanation or {}).get("status"),
        "scheduled": result.get("scheduled"),
        "error": result.get("error"),
        "call_count": (explanation or {}).get("call_count"),
        "max_calls_per_incident": int(
            (risk_policy.raw.get("llm") or {}).get("max_calls_per_incident", 2)
        ),
    }


@app.post("/api/incidents/{incident_id}/feedback")
def incident_feedback(
    incident_id: str,
    body: IncidentFeedbackBody,
    x_omniguard_operator: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_omniguard_operator != OPERATOR_TOKEN:
        raise HTTPException(status_code=401, detail="Operator authorization required")
    if body.classification not in FEEDBACK:
        raise HTTPException(status_code=400, detail="Invalid classification")
    incident = incident_store.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    feedback = {
        "classification": body.classification,
        "notes": body.notes,
        "at": now(),
    }
    status = "FALSE_POSITIVE" if body.classification == "FALSE_POSITIVE" else incident["status"]
    if body.classification == "CONFIRMED_ATTACK" and status not in {"RESOLVED", "RECOVERING"}:
        status = "AWAITING_VERIFICATION"
    updated = incident_store.update_fields(
        incident_id, human_feedback_json=feedback, status=status
    )
    return {"ok": True, "incident": updated}


@app.post("/api/incidents/{incident_id}/recover")
def incident_recover(
    incident_id: str,
    body: RecoveryBody,
    x_omniguard_operator: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_omniguard_operator != OPERATOR_TOKEN:
        raise HTTPException(status_code=401, detail="Operator authorization required")
    if not incident_store.get(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    if not body.evidence and not body.force_state:
        return recovery_manager.start(incident_id)
    return recovery_manager.advance(
        incident_id, evidence_updates=body.evidence, force_state=body.force_state
    )


def _run_malicious_manipulation_scenario() -> dict[str, Any]:
    """valid_identity_malicious_manipulation demonstration sequence."""
    reset_state()
    start = teleop_manager.start(
        {
            "credential": VALID_TOKEN,
            "agent_id": "fleet-agent-01",
            "device_id": KNOWN_DEVICE,
            "robot_id": "robot-01",
            "x": 0.0,
            "y": 0.0,
            "speed": 0.8,
        }
    )
    if start.get("final_decision") != "ALLOW" or not start.get("control_id"):
        return {"scenario": "valid_identity_malicious_manipulation", "start": start}
    cid = start["control_id"]
    steps: list[dict[str, Any]] = []
    seq = 0

    def move(x: float, y: float) -> dict[str, Any]:
        nonlocal seq
        seq += 1
        return teleop_manager.move(
            {
                "control_id": cid,
                "sequence": seq,
                "robot_id": "robot-01",
                "x": x,
                "y": y,
                "speed": 0.8,
            }
        )

    steps.append({"action": "BASE_MOVE", "result": move(1.0, 0.0)})
    steps.append(
        {
            "action": "ARM_PRESET_reach",
            "result": teleop_manager.arm_preset(
                {"control_id": cid, "robot_id": "robot-01", "preset": "reach"}
            ),
        }
    )
    steps.append(
        {
            "action": "GRIPPER_OPEN",
            "result": teleop_manager.gripper(
                {"control_id": cid, "robot_id": "robot-01", "action": "open"}
            ),
        }
    )
    steps.append(
        {
            "action": "GRIPPER_CLOSE",
            "result": teleop_manager.gripper(
                {"control_id": cid, "robot_id": "robot-01", "action": "close"}
            ),
        }
    )
    steps.append(
        {
            "action": "ARM_PRESET_carry",
            "result": teleop_manager.arm_preset(
                {"control_id": cid, "robot_id": "robot-01", "preset": "carry"}
            ),
        }
    )
    steps.append({"action": "BASE_MOVE", "result": move(2.0, 0.0)})

    blocked = next(
        (
            s
            for s in steps
            if s["result"].get("final_decision") == "BLOCK"
            or (
                s["result"].get("status") == "REJECTED"
                and "AI_BLOCK" in (s["result"].get("reasons") or [])
            )
        ),
        None,
    )
    if blocked is None:
        blocked = next(
            (
                s
                for s in steps
                if s["result"].get("status") in {"REJECTED", "PAUSED_FOR_REVIEW"}
                and s["result"].get("final_decision") in {"BLOCK", "HOLD"}
            ),
            steps[-1],
        )
    incidents = incident_store.list(limit=1)
    return {
        "scenario": "valid_identity_malicious_manipulation",
        "final_decision": blocked["result"].get("final_decision")
        or (
            "BLOCK"
            if blocked["result"].get("status") == "REJECTED"
            else blocked["result"].get("status")
        ),
        "decision_source": blocked["result"].get("decision_source"),
        "hard_policy_would_block": blocked["result"].get("hard_policy_would_block", False),
        "anomaly_risk_score": blocked["result"].get("anomaly_risk_score"),
        "behavioral_rule_score": blocked["result"].get("behavioral_rule_score"),
        "effective_risk": blocked["result"].get("effective_risk"),
        "caught_by": blocked["result"].get("caught_by"),
        "response_playbook": blocked["result"].get("response_playbook"),
        "incident_id": blocked["result"].get("incident_id")
        or (incidents[0]["incident_id"] if incidents else None),
        "steps": steps,
        "policy_decision": blocked["result"].get("policy_decision"),
        "reasons": blocked["result"].get("reasons") or [],
        "containment": (incidents[0].get("containment") if incidents else None),
        "actions": (incidents[0].get("containment") or {}).get("acknowledged", [])
        if incidents
        else [],
        "unverified_actions": (incidents[0].get("containment") or {}).get(
            "unverified", []
        )
        if incidents
        else [],
    }


@app.get("/api/robots/robot-01/next-command")
def next_robot_command(
    x_omniguard_simulator: str | None = Header(default=None),
) -> dict[str, Any]:
    require_simulator(x_omniguard_simulator)
    with _LOCK:
        if not STATE["command_queue"]:
            return {"action": "NONE"}
        return STATE["command_queue"].pop(0)


@app.post("/api/robots/robot-01/telemetry")
def telemetry(
    data: Telemetry,
    x_omniguard_simulator: str | None = Header(default=None),
) -> dict[str, str]:
    require_simulator(x_omniguard_simulator)
    with _LOCK:
        contained = STATE["robot_status"] in {"CONTAINED", "CONTAINMENT_FAILED"}
        revoked = STATE["credential_status"] == "REVOKED"
        if contained and revoked and data.status not in {"CONTAINED", "STOPPED"}:
            raise HTTPException(
                status_code=409,
                detail="Robot is contained; reset the demo before accepting motion telemetry",
            )
        STATE["robot_status"] = data.status
        STATE["robot_zone"] = data.zone
        if data.speed is not None:
            STATE["robot_speed"] = data.speed
        if data.status == "CONTAINED":
            STATE["robot_speed"] = 0.0
            STATE["last_containment_ack"] = now()
        return {"status": "accepted"}
