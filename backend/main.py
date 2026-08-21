from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.actuation import maybe_actuate_move, maybe_actuate_stop
from backend.anomaly import detector
from backend.incident_ai import explain_incident, llm_status
from backend.policy import (
    KNOWN_DEVICE,
    RESTRICTED_ZONE,
    SAFE_ZONES,
    VALID_TOKEN,
    collect_reasons,
    decide,
)
from backend.scenarios import get_scenario, list_scenarios


# Local/hackathon demo API. Prefer private bind (run_demo.sh uses 127.0.0.1).
# For signed credentials use broker.main:app (JWT) on :8001.
SIMULATOR_TOKEN = os.getenv("OMNIGUARD_SIMULATOR_TOKEN", "omniguard-sim")

app = FastAPI(
    title="OmniGuard API",
    version="0.2.1",
    description=(
        "LOCAL DEMO broker for the four-button hackathon path. "
        "Demo credential is a shared secret (OMNIGUARD_DEMO_TOKEN), not a signed JWT. "
        "Do not expose on the public internet. Use broker/ JWT path for claim verification."
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
    hour_of_day: int | None = Field(default=None, ge=0, le=23)
    seconds_since_last_command: float | None = Field(default=None, ge=0)
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
        return public_state_unlocked()


def public_state_unlocked() -> dict[str, Any]:
    return {key: value for key, value in STATE.items() if key != "command_queue"}


def public_state() -> dict[str, Any]:
    with _LOCK:
        return public_state_unlocked()


def evaluate(command: CommandRequest) -> dict[str, Any]:
    with _LOCK:
        known_device = command.device_id == KNOWN_DEVICE
        restricted = command.destination not in SAFE_ZONES
        now_dt = datetime.now(timezone.utc)
        hour = (
            command.hour_of_day
            if command.hour_of_day is not None
            else now_dt.hour
        )
        if command.seconds_since_last_command is not None:
            gap = float(command.seconds_since_last_command)
        elif STATE.get("last_command_at"):
            try:
                prev = datetime.fromisoformat(STATE["last_command_at"])
                gap = max(0.0, (now_dt - prev).total_seconds())
            except ValueError:
                gap = 30.0
        else:
            gap = 30.0

        risk, features, ai_info = detector.score(
            speed=command.speed,
            known_device=known_device,
            restricted_destination=restricted,
            commands_last_10_seconds=command.commands_last_10_seconds,
            previous_failures=command.previous_failures,
            hour_of_day=hour,
            seconds_since_last_command=gap,
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
        hard_policy_would_block = any(
            r in {
                "INVALID_CREDENTIAL",
                "REVOKED_CREDENTIAL",
                "UNAUTHORIZED_AGENT",
                "UNAUTHORIZED_ROBOT",
                "UNKNOWN_DEVICE",
                "RESTRICTED_DESTINATION",
                "EXCESSIVE_SPEED",
            }
            for r in reasons
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
            STATE["robot_status"] = "MOVING"
            # Zone updates from simulator telemetry (or Isaac push ack below).
            actuation = maybe_actuate_move(
                command.robot_id, command.destination, command.speed
            )
            if actuation is False:
                actions.append("ISAAC_ACTUATION_FAILED")
                STATE["robot_status"] = "MOVE_FAILED"
            elif actuation is True:
                actions.append("ISAAC_MOVE_SENT")
                # Push path has no fake_robot telemetry — reflect intent honestly.
                STATE["robot_zone"] = command.destination
                STATE["robot_status"] = "MOVING"
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
            "hard_policy_would_block": hard_policy_would_block,
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
            "caught_by": (
                "hard_policy"
                if hard_policy_would_block and decision == "BLOCK"
                else (
                    "ai_anomaly"
                    if decision == "BLOCK" and not hard_policy_would_block
                    else "none"
                )
            ),
        }
        if decision == "BLOCK":
            event["incident_explanation"] = explain_incident(event)
        STATE["last_command_at"] = event["timestamp"]
        STATE["events"].insert(0, event)
        STATE["events"] = STATE["events"][:100]
        return event


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "omniguard",
        "mode": "local-demo",
        "robot_backend": os.getenv("OMNIGUARD_ROBOT_BACKEND", "mock"),
        "isaac_bridge_url": os.getenv("ISAAC_BRIDGE_URL", "http://127.0.0.1:8899"),
        "llm": llm_status(),
        "anomaly": detector.status(),
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
        # Ensure a revoked credential exists for the replay demo.
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
                    commands_last_10_seconds=8,
                    previous_failures=3,
                    protection_enabled=True,
                )
            )

    return evaluate(
        CommandRequest(
            credential=scenario["credential"],
            agent_id=scenario["agent_id"],
            device_id=scenario["device_id"],
            robot_id=scenario["robot_id"],
            destination=scenario["destination"],
            speed=scenario["speed"],
            commands_last_10_seconds=scenario["commands_last_10_seconds"],
            previous_failures=scenario["previous_failures"],
            hour_of_day=scenario.get("hour_of_day"),
            seconds_since_last_command=scenario.get("seconds_since_last_command"),
            protection_enabled=protection,
        )
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
            commands_last_10_seconds=10,
            previous_failures=4,
            hour_of_day=3,
            seconds_since_last_command=1.5,
            protection_enabled=True,
        )
    )


@app.get("/api/state")
def state() -> dict[str, Any]:
    return public_state()


@app.get("/api/events")
def events() -> list[dict[str, Any]]:
    with _LOCK:
        return list(STATE["events"])


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
