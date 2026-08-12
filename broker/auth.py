import time
import uuid

import jwt

# Demo-only secret. In a real deployment this comes from a secret manager,
# and the algorithm would likely be RS256 with per-issuer key rotation.
SECRET_KEY = "omniguard-hackathon-demo-secret"
ALGORITHM = "HS256"


class TokenError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def issue_token(
    sub: str,
    robots: list[str],
    zones: list[str],
    max_speed: float,
    device_id: str,
    human_zone_authorized: bool = False,
    ttl_seconds: int = 3600,
) -> str:
    now = int(time.time())
    claims = {
        "sub": sub,
        "robots": robots,
        "zones": zones,
        "max_speed": max_speed,
        "device_id": device_id,
        "human_zone_authorized": human_zone_authorized,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenError("TOKEN_EXPIRED", "Token has expired")
    except jwt.InvalidTokenError:
        raise TokenError("TOKEN_INVALID", "Token signature/claims are invalid")
