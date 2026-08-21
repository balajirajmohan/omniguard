"""Server-trusted behavioral feature derivation for anomaly scoring.

Callers must not supply command frequency, failure counts, hour, or gap.
Scenario runners may inject a BehaviorContext for controlled demos only.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


WINDOW_SECONDS = 10.0


@dataclass(frozen=True)
class BehaviorContext:
    commands_last_10_seconds: int
    previous_failures: int
    hour_of_day: int
    seconds_since_last_command: float
    source: str = "server"  # "server" | "scenario"

    def as_features(self) -> dict[str, float]:
        return {
            "commands_last_10_seconds": float(self.commands_last_10_seconds),
            "previous_failures": float(self.previous_failures),
            "hour_of_day": float(self.hour_of_day),
            "seconds_since_last_command": float(self.seconds_since_last_command),
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BehaviorTracker:
    def __init__(self, window_seconds: float = WINDOW_SECONDS) -> None:
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._timestamps: dict[str, deque[datetime]] = defaultdict(deque)
        self._failures: dict[str, int] = defaultdict(int)
        self._last_at: dict[str, datetime] = {}

    def reset(self) -> None:
        with self._lock:
            self._timestamps.clear()
            self._failures.clear()
            self._last_at.clear()

    def _key(self, agent_id: str, device_id: str) -> str:
        return f"{agent_id}|{device_id}"

    def record_failure(self, agent_id: str, device_id: str) -> None:
        with self._lock:
            self._failures[self._key(agent_id, device_id)] += 1

    def snapshot(
        self,
        *,
        agent_id: str,
        device_id: str,
        now: datetime | None = None,
        override: BehaviorContext | None = None,
    ) -> BehaviorContext:
        """Return features for this command, then record the command timestamp.

        When override is provided (scenario/demo only), those values are used for
        scoring but the command is still recorded for subsequent server history.
        """
        now = now or datetime.now(timezone.utc)
        key = self._key(agent_id, device_id)
        with self._lock:
            if override is not None:
                ctx = BehaviorContext(
                    commands_last_10_seconds=override.commands_last_10_seconds,
                    previous_failures=override.previous_failures,
                    hour_of_day=override.hour_of_day,
                    seconds_since_last_command=override.seconds_since_last_command,
                    source="scenario",
                )
            else:
                q = self._timestamps[key]
                while q and (now - q[0]).total_seconds() > self.window_seconds:
                    q.popleft()
                count = len(q)
                if key in self._last_at:
                    gap = max(0.0, (now - self._last_at[key]).total_seconds())
                else:
                    gap = 30.0
                ctx = BehaviorContext(
                    commands_last_10_seconds=count,
                    previous_failures=int(self._failures[key]),
                    hour_of_day=now.hour,
                    seconds_since_last_command=round(gap, 3),
                    source="server",
                )

            self._timestamps[key].append(now)
            self._last_at[key] = now
            return ctx


behavior_tracker = BehaviorTracker()
