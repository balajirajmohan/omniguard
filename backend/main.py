from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.anomaly import detector
from backend.actuation import maybe_actuate_move, maybe_actuate_stop
from backend.incident_ai import explain_incident
from backend.policy import (
    KNOWN_DEVICE,
    RESTRICTED_ZONE,
    VALID_TOKEN,
    collect_reasons,
    decide,
)

app = FastAPI(
    title="OmniGuard API",
    version="0.2.0",
    description=(
        "Cyber-physical security broker for warehouse robots. "
        "AI scores anomalies; deterministic policy blocks, stops and revokes."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    }


STATE = initial_state()


class CommandRequest(BaseModel):
    credential: str
    agent_id: str = "fleet-agent-01"
    device_id: str
    robot_id: str = "robot-01"
    destination: str
    speed: float = Field(ge=0, le=10)
    commands_last_10_seconds: int = 1
    previous_failures: int = 0
    protection_enabled: bool = True


class Telemetry(BaseModel):
    status: str
    zone: str
    speed: float | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_state() -> dict[str, Any]:
    STATE.clear()
    STATE.update(initial_state())
    return public_state()


def public_state() -> dict[str, Any]:
    return {key: value for key, value in STATE.items() if key != "command_queue"}


def evaluate(command: CommandRequest) -> dict[str, Any]:
    known_device = command.device_id == KNOWN_DEVICE
    restricted = command.destination == RESTRICTED_ZONE
    risk, features = detector.score(
        speed=command.speed,
        known_device=known_device,
        restricted_destination=restricted,
        commands_last_10_seconds=command.commands_last_10_seconds,
        previous_failures=command.previous_failures,
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

    STATE["protection_enabled"] = command.protection_enabled
    outcome = decide(
        protection_enabled=command.protection_enabled,
        reasons=reasons,
        risk=risk,
    )

    decision = outcome["final_decision"]
    actions = list(outcome["actions"])

    if decision == "ALLOW":
        STATE["command_queue"].append(
            {
                "action": "MOVE",
                "destination": command.destination,
                "speed": command.speed,
            }
        )
        STATE["robot_speed"] = command.speed
        actuation = maybe_actuate_move(
            command.robot_id, command.destination, command.speed
        )
        if actuation is False:
            actions.append("ISAAC_ACTUATION_FAILED")
            STATE["robot_status"] = "MOVE_FAILED"
        elif actuation is True:
            actions.append("ISAAC_MOVE_SENT")
    elif outcome["contain"]:
        STATE["command_queue"].clear()
        STATE["command_queue"].append({"action": "STOP"})
        STATE["robot_status"] = "CONTAINED"
        STATE["robot_speed"] = 0.0
        STATE["credential_status"] = "REVOKED"
        STATE["agent_status"] = "QUARANTINED"
        STATE["last_containment_ack"] = "STOP_QUEUED"
        actuation = maybe_actuate_stop(command.robot_id)
        if actuation is False:
            actions.append("ISAAC_ESTOP_FAILED")
            STATE["robot_status"] = "CONTAINMENT_FAILED"
            STATE["last_containment_ack"] = "ESTOP_FAILED"
        elif actuation is True:
            actions.append("ISAAC_ESTOP_SENT")
            STATE["last_containment_ack"] = "ESTOP_SENT"
    # HOLD: do not forward, do not revoke

    event: dict[str, Any] = {
        "timestamp": now(),
        "agent_id": command.agent_id,
        "device_id": command.device_id,
        "robot_id": command.robot_id,
        "destination": command.destination,
        "speed": command.speed,
        "credential_valid": command.credential == VALID_TOKEN,
        "policy_decision": outcome["policy_decision"],
        "anomaly_model": "IsolationForest",
        "anomaly_risk_score": risk,
        "anomaly_features": features,
        "final_decision": decision,
        "reasons": reasons,
        "actions": actions,
        "containment_actions": actions if outcome["contain"] else [],
    }
    if decision == "BLOCK":
        event["incident_explanation"] = explain_incident(event)
    STATE["events"].insert(0, event)
    STATE["events"] = STATE["events"][:100]
    return event


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "omniguard"}


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
        )
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
            commands_last_10_seconds=8,
            previous_failures=3,
            protection_enabled=protection,
        )
    )


@app.get("/api/state")
def state() -> dict[str, Any]:
    return public_state()


@app.get("/api/events")
def events() -> list[dict[str, Any]]:
    return STATE["events"]


@app.get("/api/robots/robot-01/next-command")
def next_robot_command() -> dict[str, Any]:
    if not STATE["command_queue"]:
        return {"action": "NONE"}
    return STATE["command_queue"].pop(0)


@app.post("/api/robots/robot-01/telemetry")
def telemetry(data: Telemetry) -> dict[str, str]:
    STATE["robot_status"] = data.status
    STATE["robot_zone"] = data.zone
    if data.speed is not None:
        STATE["robot_speed"] = data.speed
    if data.status == "CONTAINED":
        STATE["robot_speed"] = 0.0
        STATE["last_containment_ack"] = now()
    return {"status": "accepted"}
