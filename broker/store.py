from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Deque
from uuid import uuid4

from broker.config import ZONES
from broker.models import Decision, SecurityEvent


class EventStore:
    """In-memory revocation list, quarantine set, and event timeline."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.revoked_tokens: set[str] = set()
        self.quarantined_identities: set[str] = set()
        self.events: list[SecurityEvent] = []
        self._command_times: dict[str, Deque[float]] = {}
        self.robot_zone = "ZONE_A"
        self.robot_speed = 0.0
        self.robot_status = "IDLE"
        self.robot_last_command: str | None = None
        self.quarantined_for_robot: str | None = None

    def revoke(self, jti: str) -> None:
        with self._lock:
            self.revoked_tokens.add(jti)

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            return jti in self.revoked_tokens

    def quarantine(self, identity: str) -> None:
        with self._lock:
            self.quarantined_identities.add(identity)
            self.quarantined_for_robot = identity

    def is_quarantined(self, identity: str) -> bool:
        with self._lock:
            return identity in self.quarantined_identities

    def record_command_attempt(self, identity: str) -> None:
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            bucket = self._command_times.setdefault(identity, deque())
            bucket.append(now)

    def command_burst(self, identity: str, window_seconds: int, threshold: int) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            bucket = self._command_times.setdefault(identity, deque())
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            return len(bucket) >= threshold

    def add_event(
        self,
        *,
        event_type: str,
        message: str,
        decision: Decision | None = None,
        identity: str | None = None,
        token_jti: str | None = None,
        robot_id: str | None = None,
        destination_zone: str | None = None,
        device_id: str | None = None,
        risk_score: float = 0.0,
        contained: bool = False,
    ) -> SecurityEvent:
        event = SecurityEvent(
            id=str(uuid4()),
            event_type=event_type,
            decision=decision,
            identity=identity,
            token_jti=token_jti,
            robot_id=robot_id,
            destination_zone=destination_zone,
            device_id=device_id,
            message=message,
            risk_score=risk_score,
            contained=contained,
            timestamp=datetime.now(timezone.utc),
        )
        with self._lock:
            self.events.insert(0, event)
            self.events = self.events[:200]
        return event

    def set_robot(self, *, zone: str, speed: float, status: str, last_command: str) -> None:
        with self._lock:
            if zone in ZONES:
                self.robot_zone = zone
            self.robot_speed = speed
            self.robot_status = status
            self.robot_last_command = last_command

    def emergency_stop(self) -> None:
        with self._lock:
            self.robot_speed = 0.0
            self.robot_status = "CONTAINED"

    def reset(self) -> None:
        with self._lock:
            self.revoked_tokens.clear()
            self.quarantined_identities.clear()
            self.events.clear()
            self._command_times.clear()
            self.robot_zone = "ZONE_A"
            self.robot_speed = 0.0
            self.robot_status = "IDLE"
            self.robot_last_command = None
            self.quarantined_for_robot = None

    def snapshot_events(self, limit: int = 50) -> list[SecurityEvent]:
        with self._lock:
            return list(self.events[:limit])

    def snapshot_revoked(self) -> list[str]:
        with self._lock:
            return sorted(self.revoked_tokens)

    def snapshot_quarantined(self) -> list[str]:
        with self._lock:
            return sorted(self.quarantined_identities)
