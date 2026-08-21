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

app = FastAPI(title="OmniGuard Broker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

robot = get_robot_controller()


@app.get("/health")
def health():
    return {"status": "ok"}


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

    if result.allow:
        robot.move_to(request.robot_id, request.target_x, request.target_y, request.speed)
        state.set_robot_state(
            request.robot_id,
            position=[request.target_x, request.target_y],
            speed=request.speed,
            zone=request.target_zone,
            status="MOVING",
            last_identity=result.identity,
        )
    else:
        if result.contained:
            if result.jti:
                state.revoke(result.jti)
            if result.identity:
                state.quarantine(result.identity)
            robot.emergency_stop(request.robot_id)
            state.set_robot_state(request.robot_id, status="CONTAINED")

        incident = state.record_incident(
            identity=result.identity or "unknown",
            robot_id=request.robot_id,
            device_id=request.device_id,
            target_zone=request.target_zone,
            violations=result.violations,
            message=(
                f"{result.identity or 'unknown identity'} attempted to move "
                f"{request.robot_id} into {request.target_zone} from device "
                f"'{request.device_id}'. Command blocked"
                + (", credential revoked and robot contained." if result.contained else ".")
            ),
            contained=result.contained,
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
