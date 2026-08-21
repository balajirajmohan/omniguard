from typing import Optional

from pydantic import BaseModel


class CommandRequest(BaseModel):
    token: str
    command_id: str
    robot_id: str
    device_id: str
    target_zone: str
    target_x: float
    target_y: float
    speed: float


class CommandResponse(BaseModel):
    decision: str
    reason: str
    violations: list[str]
    incident_id: Optional[str] = None


class Incident(BaseModel):
    incident_id: str
    timestamp: float
    identity: str
    robot_id: str
    device_id: str
    target_zone: str
    violations: list[str]
    message: str
    contained: bool


class TokenIssueRequest(BaseModel):
    sub: str
    robots: list[str]
    zones: list[str]
    max_speed: float
    device_id: str
    human_zone_authorized: bool = False
    ttl_seconds: int = 3600
