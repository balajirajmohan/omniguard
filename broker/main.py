import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from broker.auth import TokenError, decode_token, issue_token
from broker.config import DEFAULT_AGENT, ZONES
from broker.isaac_adapter import IsaacAdapter
from broker.models import (
    BrokerStatus,
    CommandDecision,
    Decision,
    MoveCommand,
    RobotStatus,
    TokenIssueRequest,
    TokenIssueResponse,
)
from broker.policy import evaluate_command
from broker.store import EventStore

app = FastAPI(
    title="OmniGuard Identity Broker",
    description=(
        "Contextual AuthZ for physical AI fleets. "
        "Valid credentials can still be denied when the physical intent is unsafe."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = EventStore()
adapter = IsaacAdapter(
    store=store,
    enabled=os.getenv("OMNIGUARD_ISAAC_ENABLED", "0") == "1",
)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return authorization.split(" ", 1)[1].strip()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "omniguard-broker"}


@app.post("/tokens", response_model=TokenIssueResponse)
def create_token(body: TokenIssueRequest) -> TokenIssueResponse:
    token, claims = issue_token(
        sub=body.sub,
        robots=body.robots,
        zones=body.zones,
        max_speed=body.max_speed,
        device_id=body.device_id,
        ttl_seconds=body.ttl_seconds,
    )
    store.add_event(
        event_type="token_issued",
        identity=body.sub,
        token_jti=claims["jti"],
        device_id=body.device_id,
        message=f"Issued credential for {body.sub} bound to {body.device_id}",
    )
    return TokenIssueResponse(access_token=token, claims=claims)


@app.post("/tokens/demo-agent", response_model=TokenIssueResponse)
def create_demo_agent_token() -> TokenIssueResponse:
    """Issue the default legitimate fleet-agent credential used in demos."""
    token, claims = issue_token(**DEFAULT_AGENT)
    store.add_event(
        event_type="token_issued",
        identity=claims["sub"],
        token_jti=claims["jti"],
        device_id=claims["device_id"],
        message="Issued demo fleet-agent-01 credential",
    )
    return TokenIssueResponse(access_token=token, claims=claims)


@app.post("/commands/move", response_model=CommandDecision)
def move_robot(
    command: MoveCommand,
    authorization: str | None = Header(default=None),
) -> CommandDecision:
    raw = _bearer_token(authorization)
    try:
        claims = decode_token(raw)
    except TokenError as exc:
        store.add_event(
            event_type="auth_failure",
            decision=Decision.DENY,
            robot_id=command.robot_id,
            destination_zone=command.destination_zone,
            device_id=command.device_id,
            message=exc.message,
            risk_score=0.6,
        )
        raise HTTPException(status_code=401, detail=exc.message) from exc

    identity = claims.get("sub", "unknown")
    jti = claims.get("jti")
    store.record_command_attempt(identity)

    allowed, reasons, risk, should_contain = evaluate_command(claims, command, store)

    if allowed:
        result = adapter.execute_move(command)
        decision = CommandDecision(
            decision=Decision.ALLOW,
            reasons=reasons,
            command=command,
            identity=identity,
            token_jti=jti,
            contained=False,
            robot_action=result.action,
            risk_score=risk,
            timestamp=datetime.now(timezone.utc),
        )
        store.add_event(
            event_type="command_allowed",
            decision=Decision.ALLOW,
            identity=identity,
            token_jti=jti,
            robot_id=command.robot_id,
            destination_zone=command.destination_zone,
            device_id=command.device_id,
            message=result.detail,
            risk_score=risk,
        )
        return decision

    # Containment path
    contained = False
    robot_action = "NONE"
    if should_contain:
        if jti:
            store.revoke(jti)
        store.quarantine(identity)
        estop = adapter.emergency_stop(
            command.robot_id,
            reason="; ".join(r.message for r in reasons),
        )
        robot_action = estop.action
        contained = True

    decision = CommandDecision(
        decision=Decision.DENY,
        reasons=reasons,
        command=command,
        identity=identity,
        token_jti=jti,
        contained=contained,
        robot_action=robot_action,
        risk_score=risk,
        timestamp=datetime.now(timezone.utc),
    )
    store.add_event(
        event_type="command_denied",
        decision=Decision.DENY,
        identity=identity,
        token_jti=jti,
        robot_id=command.robot_id,
        destination_zone=command.destination_zone,
        device_id=command.device_id,
        message=(
            "Critical: credential compromise / unsafe physical intent detected. "
            + "; ".join(r.message for r in reasons)
        ),
        risk_score=risk,
        contained=contained,
    )
    return decision


@app.get("/status", response_model=BrokerStatus)
def status() -> BrokerStatus:
    return BrokerStatus(
        robot=RobotStatus(
            robot_id="robot-01",
            zone=store.robot_zone,
            speed=store.robot_speed,
            status=store.robot_status,
            last_command=store.robot_last_command,
            quarantined_identity=store.quarantined_for_robot,
        ),
        revoked_tokens=store.snapshot_revoked(),
        quarantined_identities=store.snapshot_quarantined(),
        recent_events=store.snapshot_events(),
        zones=ZONES,
    )


@app.get("/events")
def events(limit: int = 50) -> list:
    return store.snapshot_events(limit=limit)


@app.post("/demo/reset")
def reset_demo() -> dict:
    store.reset()
    store.add_event(
        event_type="demo_reset",
        message="Demo state cleared — robot returned to ZONE_A / IDLE",
    )
    return {"ok": True, "message": "Demo state reset"}
