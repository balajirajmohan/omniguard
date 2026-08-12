from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt

from broker.config import JWT_ALGORITHM, JWT_SECRET


class TokenError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def issue_token(
    *,
    sub: str,
    robots: list[str],
    zones: list[str],
    max_speed: float,
    device_id: str,
    ttl_seconds: int = 3600,
    jti: str | None = None,
) -> tuple[str, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": sub,
        "robots": robots,
        "zones": zones,
        "max_speed": max_speed,
        "device_id": device_id,
        "jti": jti or str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    token = jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, claims


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired", "Credential has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("token_invalid", "Credential is invalid") from exc
