from dataclasses import dataclass

from broker.auth import TokenError, decode_token
from broker.models import CommandRequest
from broker.state import state

HUMAN_ZONE = "HUMAN_ZONE"

# Violations that indicate credential misuse or an active attack, not just a
# malformed/edge-case request. These trigger full containment: revoke the
# token, quarantine the identity, and e-stop the robot.
CRITICAL_VIOLATIONS = {
    "TOKEN_INVALID",
    "TOKEN_EXPIRED",
    "TOKEN_REVOKED",
    "IDENTITY_QUARANTINED",
    "ROBOT_NOT_AUTHORIZED",
    "ZONE_NOT_PERMITTED",
    "HUMAN_ZONE_UNAUTHORIZED",
    "DEVICE_MISMATCH",
    "REPLAY_DETECTED",
    "COMMAND_BURST",
}


@dataclass
class PolicyResult:
    allow: bool
    violations: list[str]
    reason: str
    identity: str | None
    jti: str | None
    contained: bool


def evaluate(request: CommandRequest) -> PolicyResult:
    violations: list[str] = []

    try:
        claims = decode_token(request.token)
    except TokenError as exc:
        return PolicyResult(
            allow=False,
            violations=[exc.code],
            reason=exc.message,
            identity=None,
            jti=None,
            contained=False,
        )

    identity = claims["sub"]
    jti = claims["jti"]

    if state.is_revoked(jti):
        violations.append("TOKEN_REVOKED")
    if state.is_quarantined(identity):
        violations.append("IDENTITY_QUARANTINED")
    if request.robot_id not in claims.get("robots", []):
        violations.append("ROBOT_NOT_AUTHORIZED")
    if request.target_zone not in claims.get("zones", []):
        violations.append("ZONE_NOT_PERMITTED")
    elif request.target_zone == HUMAN_ZONE and not claims.get("human_zone_authorized", False):
        violations.append("HUMAN_ZONE_UNAUTHORIZED")
    if request.speed > claims.get("max_speed", 0):
        violations.append("SPEED_EXCEEDED")
    if request.device_id != claims.get("device_id"):
        violations.append("DEVICE_MISMATCH")
    if state.is_replay(jti, request.command_id):
        violations.append("REPLAY_DETECTED")
    if state.is_burst(identity):
        violations.append("COMMAND_BURST")

    allow = not violations
    contained = any(v in CRITICAL_VIOLATIONS for v in violations)

    if allow:
        reason = "Command satisfies token, zone, speed and device policy."
    else:
        reason = f"Denied: {', '.join(violations)}"

    return PolicyResult(
        allow=allow,
        violations=violations,
        reason=reason,
        identity=identity,
        jti=jti,
        contained=contained,
    )
