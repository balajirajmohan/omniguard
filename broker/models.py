from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class MoveCommand(BaseModel):
    robot_id: str = Field(..., examples=["robot-01"])
    destination_zone: str = Field(..., examples=["ZONE_B"])
    speed: float = Field(..., ge=0.0, examples=[1.0])
    device_id: str = Field(..., examples=["controller-01"])


class PolicyReason(BaseModel):
    code: str
    message: str


class CommandDecision(BaseModel):
    decision: Decision
    reasons: list[PolicyReason]
    command: MoveCommand
    identity: Optional[str] = None
    token_jti: Optional[str] = None
    contained: bool = False
    robot_action: Optional[str] = None
    risk_score: float = 0.0
    timestamp: datetime


class TokenIssueRequest(BaseModel):
    sub: str = "fleet-agent-01"
    robots: list[str] = Field(default_factory=lambda: ["robot-01"])
    zones: list[str] = Field(default_factory=lambda: ["ZONE_A", "ZONE_B"])
    max_speed: float = 1.5
    device_id: str = "controller-01"
    ttl_seconds: int = 3600


class TokenIssueResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    claims: dict[str, Any]


class SecurityEvent(BaseModel):
    id: str
    event_type: str
    decision: Optional[Decision] = None
    identity: Optional[str] = None
    token_jti: Optional[str] = None
    robot_id: Optional[str] = None
    destination_zone: Optional[str] = None
    device_id: Optional[str] = None
    message: str
    risk_score: float = 0.0
    contained: bool = False
    timestamp: datetime


class RobotStatus(BaseModel):
    robot_id: str
    zone: str
    speed: float
    status: str
    last_command: Optional[str] = None
    quarantined_identity: Optional[str] = None


class BrokerStatus(BaseModel):
    robot: RobotStatus
    revoked_tokens: list[str]
    quarantined_identities: list[str]
    recent_events: list[SecurityEvent]
    zones: dict[str, Any]
