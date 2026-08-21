import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from broker import auth
from broker.models import CommandRequest, CommandResponse, TokenIssueRequest
from broker.policy import evaluate
from broker.robot_adapter import get_robot_controller
from broker.state import state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("omniguard.broker")

app = FastAPI(
    title="OmniGuard JWT Broker",
    description=(
        "Srikanth's JWT Zero-Trust broker with mock/Isaac robot adapter. "
        "For the four-button hackathon demo, prefer backend.main:app on :8000."
    ),
    version="0.1.1",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

robot = get_robot_controller()


@app.get("/health")
def health():
    return {"status": "ok", "service": "omniguard-jwt-broker"}


@app.post("/token")
def create_token(req: TokenIssueRequest):
    """Demo helper to mint credentials. A real deployment issues these from
    an identity provider, never from the broker itself."""
    token = auth.issue_token(
        sub=req.sub,
        robots=req.robots,
        zones=req.zones,
        max_speed=req.max_speed,
        device_id=req.device_id,
        human_zone_authorized=req.human_zone_authorized,
        ttl_seconds=req.ttl_seconds,
    )
    return {"token": token}


@app.post("/command", response_model=CommandResponse)
def submit_command(request: CommandRequest):
    result = evaluate(request)

    incident_id = None
    actually_contained = False

    if result.allow:
        previous = state.snapshot().get("robot_state", {}).get(request.robot_id, {})
        moved = robot.move_to(
            request.robot_id, request.target_x, request.target_y, request.speed
        )
        if moved:
            state.set_robot_state(
                request.robot_id,
                position=[request.target_x, request.target_y],
                speed=request.speed,
                zone=request.target_zone,
                status="MOVING",
                last_identity=result.identity,
                actuation_ok=True,
            )
        else:
            # Keep last known pose; do not pretend we arrived.
            state.set_robot_state(
                request.robot_id,
                position=previous.get("position"),
                speed=0.0,
                zone=previous.get("zone"),
                status="MOVE_FAILED",
                last_identity=result.identity,
                actuation_ok=False,
            )
            logger.error("ALLOW issued but robot actuation failed for %s", request.robot_id)
    else:
        if result.contained:
            if result.jti:
                state.revoke(result.jti)
            if result.identity:
                state.quarantine(result.identity)
            stopped = robot.emergency_stop(request.robot_id)
            actually_contained = bool(stopped)
            state.set_robot_state(
                request.robot_id,
                status="CONTAINED" if stopped else "CONTAINMENT_FAILED",
                speed=0.0,
                actuation_ok=stopped,
            )
            if not stopped:
                logger.error(
                    "Containment requested but e-stop failed for %s", request.robot_id
                )

        if result.contained and actually_contained:
            contain_msg = ", credential revoked and robot contained."
        elif result.contained and not actually_contained:
            contain_msg = (
                ", credential revoked but robot e-stop FAILED — operator intervention required."
            )
        else:
            contain_msg = "."

        incident = state.record_incident(
            identity=result.identity or "unknown",
            robot_id=request.robot_id,
            device_id=request.device_id,
            target_zone=request.target_zone,
            violations=result.violations,
            message=(
                f"{result.identity or 'unknown identity'} attempted to move "
                f"{request.robot_id} into {request.target_zone} from device "
                f"'{request.device_id}'. Command blocked{contain_msg}"
            ),
            contained=actually_contained if result.contained else False,
        )
        incident_id = incident["incident_id"]
        logger.warning("DENY %s: %s", request.robot_id, result.reason)

    return CommandResponse(
        decision="ALLOW" if result.allow else "DENY",
        reason=result.reason,
        violations=result.violations,
        incident_id=incident_id,
    )


@app.get("/state")
def get_state():
    return state.snapshot()


@app.post("/reset")
def reset_state():
    state.reset()
    return {"status": "reset"}
