from __future__ import annotations

import os
import threading
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

SIMULATOR_TOKEN = os.getenv("OMNIGUARD_SIMULATOR_TOKEN", "omniguard-sim")

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
        "events": [],
        "command_queue": [{"action": "RESET"}],
        "last_containment_ack": None,
        "last_command_at": None,
        "timeline": [],
    }


STATE = initial_state()


class CommandRequest(BaseModel):
    """Real command properties only — behavioral history is server-derived."""

    model_config = ConfigDict(extra="forbid")

    credential: str
    agent_id: str = "fleet-agent-01"
    device_id: str
    robot_id: str = "robot-01"
    destination: str
    speed: float = Field(ge=0, le=10)
    protection_enabled: bool = True


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


def reset_state() -> dict[str, Any]:
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
    behavior_override: BehaviorContext | None = None,
) -> dict[str, Any]:
    with _LOCK:
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
            credential_status=STATE["credential_status"],
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

        STATE["protection_enabled"] = command.protection_enabled
        outcome = decide(
            protection_enabled=command.protection_enabled,
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
            actuation = maybe_actuate_move(
                command.robot_id, command.destination, command.speed
            )
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
            actuation = maybe_actuate_stop(command.robot_id)
            if actuation is None:
                # Mock / fake-robot path: request only; physical stop via poll queue.
                actions.append("STOP_QUEUED_FOR_SIMULATOR")
                STATE["last_containment_ack"] = "STOP_QUEUED"
            elif actuation.stage == "FAILED" or not actuation.ok:
                actions.append("ISAAC_ESTOP_FAILED")
                STATE["robot_status"] = "CONTAINMENT_FAILED"
                STATE["last_containment_ack"] = "ESTOP_FAILED"
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
            "timeline": list(reversed(timeline_steps)),
        }
        if decision == "BLOCK":
            event["incident_explanation"] = explain_incident(event)
        _append_timeline(timeline_steps)
        STATE["last_command_at"] = event["timestamp"]
        STATE["events"].insert(0, event)
        STATE["events"] = STATE["events"][:100]
        return event


@app.get("/health")
def health() -> dict[str, Any]:
    anomaly = detector.status()
    return {
        "status": "ok",
        "service": "omniguard",
        "mode": "local-demo",
        "robot_backend": os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock"),
        "isaac_bridge_url": os.getenv("ISAAC_BRIDGE_URL", "http://127.0.0.1:8899"),
        "llm": llm_status(),
        "anomaly": anomaly,
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
) -> dict[str, Any]:
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
                    protection_enabled=True,
                ),
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
            protection_enabled=protection,
        ),
        behavior_override=_scenario_behavior(scenario),
    )


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    return reset_state()


@app.post("/api/commands")
def commands(command: CommandRequest) -> dict[str, Any]:
    return evaluate(command)


@app.post("/api/demo/normal")
def demo_normal() -> dict[str, Any]:
    reset_state()
    return evaluate(
        CommandRequest(
            credential=VALID_TOKEN,
            device_id=KNOWN_DEVICE,
            destination="SAFE_ZONE_B",
            speed=0.8,
            protection_enabled=True,
        ),
        behavior_override=BehaviorContext(
            commands_last_10_seconds=1,
            previous_failures=0,
            hour_of_day=10,
            seconds_since_last_command=40.0,
            source="scenario",
        ),
    )


@app.post("/api/demo/attack")
def demo_attack(protection: bool = Query(default=True)) -> dict[str, Any]:
    reset_state()
    return evaluate(
        CommandRequest(
            credential=VALID_TOKEN,
            device_id="unknown-attacker-device",
            destination=RESTRICTED_ZONE,
            speed=3.5,
            protection_enabled=protection,
        ),
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
            protection_enabled=True,
        ),
        behavior_override=BehaviorContext(
            commands_last_10_seconds=10,
            previous_failures=4,
            hour_of_day=3,
            seconds_since_last_command=1.5,
            source="scenario",
        ),
    )


@app.get("/api/state")
def state() -> dict[str, Any]:
    payload = public_state()
    bridge = fetch_bridge_state()
    if bridge is not None:
        payload["isaac_bridge_state"] = bridge
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


@app.get("/api/incidents/latest")
def latest_incident() -> dict[str, Any]:
    with _LOCK:
        for event in STATE["events"]:
            if event.get("final_decision") == "BLOCK":
                return {
                    "incident": event,
                    "exported_at": now(),
                }
        return {"incident": None, "exported_at": now()}


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
