from broker.config import RESTRICTED_ZONES, ZONES
from broker.models import MoveCommand, PolicyReason
from broker.store import EventStore


def evaluate_command(
    claims: dict,
    command: MoveCommand,
    store: EventStore,
) -> tuple[bool, list[PolicyReason], float, bool]:
    """Return (allowed, reasons, risk_score, should_contain).

    Decision order:
    1. token unrevoked
    2. robot allowed
    3. destination zone permitted
    4. speed within limit
    5. device matches credential
    6. anomaly checks (restricted zone intent, rogue device, burst)
    """
    reasons: list[PolicyReason] = []
    risk = 0.0
    jti = claims.get("jti")
    sub = claims.get("sub", "unknown")

    if jti and store.is_revoked(jti):
        reasons.append(
            PolicyReason(code="token_revoked", message="Credential has been revoked")
        )
        return False, reasons, 1.0, True

    if store.is_quarantined(sub):
        reasons.append(
            PolicyReason(
                code="identity_quarantined",
                message=f"Identity {sub} is quarantined after prior containment",
            )
        )
        return False, reasons, 1.0, True

    allowed_robots = set(claims.get("robots") or [])
    if command.robot_id not in allowed_robots:
        reasons.append(
            PolicyReason(
                code="robot_forbidden",
                message=f"Identity may not control {command.robot_id}",
            )
        )
        risk = max(risk, 0.8)

    allowed_zones = set(claims.get("zones") or [])
    if command.destination_zone not in ZONES:
        reasons.append(
            PolicyReason(
                code="zone_unknown",
                message=f"Unknown destination zone {command.destination_zone}",
            )
        )
        risk = max(risk, 0.7)
    elif command.destination_zone not in allowed_zones:
        reasons.append(
            PolicyReason(
                code="zone_forbidden",
                message=(
                    f"Destination {command.destination_zone} is outside token zone grant"
                ),
            )
        )
        risk = max(risk, 0.95)

    if command.destination_zone in RESTRICTED_ZONES:
        reasons.append(
            PolicyReason(
                code="human_zone_breach",
                message="Command targets HUMAN_ZONE — potential cyber-to-physical harm",
            )
        )
        risk = max(risk, 0.99)

    max_speed = float(claims.get("max_speed", 0))
    if command.speed > max_speed:
        reasons.append(
            PolicyReason(
                code="speed_exceeded",
                message=f"Requested speed {command.speed} exceeds max_speed {max_speed}",
            )
        )
        risk = max(risk, 0.7)

    bound_device = claims.get("device_id")
    if command.device_id != bound_device:
        reasons.append(
            PolicyReason(
                code="device_mismatch",
                message=(
                    f"Command device {command.device_id} does not match "
                    f"credential device {bound_device}"
                ),
            )
        )
        risk = max(risk, 0.9)

    if store.command_burst(sub, window_seconds=5, threshold=5):
        reasons.append(
            PolicyReason(
                code="command_burst",
                message="Abnormal command burst detected for this identity",
            )
        )
        risk = max(risk, 0.75)

    # Contextual compromise: valid token + rogue device and/or restricted zone
    compromise_signals = {
        "device_mismatch",
        "human_zone_breach",
        "zone_forbidden",
    }
    should_contain = any(r.code in compromise_signals for r in reasons)
    allowed = len(reasons) == 0

    if allowed:
        reasons.append(
            PolicyReason(code="policy_ok", message="Command satisfies contextual policy")
        )
        risk = 0.05

    return allowed, reasons, risk, should_contain
