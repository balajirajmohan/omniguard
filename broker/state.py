import threading
import time
import uuid
from collections import defaultdict, deque

BURST_WINDOW_SECONDS = 5
BURST_THRESHOLD = 4


class OmniGuardState:
    """In-memory state for the hackathon MVP.

    Everything lives in process memory and resets with the broker.
    A real deployment would back the revocation list and incident log
    with SQLite/Redis, but the demo only needs a single process.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.revoked_jtis: set[str] = set()
        self.quarantined_identities: set[str] = set()
        self.seen_command_ids: dict[str, set[str]] = defaultdict(set)
        self.command_timestamps: dict[str, deque] = defaultdict(deque)
        self.incidents: list[dict] = []
        self.robot_state: dict[str, dict] = {}

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            return jti in self.revoked_jtis

    def is_quarantined(self, identity: str) -> bool:
        with self._lock:
            return identity in self.quarantined_identities

    def revoke(self, jti: str):
        with self._lock:
            self.revoked_jtis.add(jti)

    def quarantine(self, identity: str):
        with self._lock:
            self.quarantined_identities.add(identity)

    def is_replay(self, jti: str, command_id: str) -> bool:
        with self._lock:
            seen = self.seen_command_ids[jti]
            if command_id in seen:
                return True
            seen.add(command_id)
            return False

    def is_burst(self, identity: str) -> bool:
        now = time.time()
        with self._lock:
            history = self.command_timestamps[identity]
            history.append(now)
            while history and now - history[0] > BURST_WINDOW_SECONDS:
                history.popleft()
            return len(history) > BURST_THRESHOLD

    def record_incident(
        self,
        identity: str,
        robot_id: str,
        device_id: str,
        target_zone: str,
        violations: list[str],
        message: str,
        contained: bool,
    ) -> dict:
        incident = {
            "incident_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "identity": identity,
            "robot_id": robot_id,
            "device_id": device_id,
            "target_zone": target_zone,
            "violations": violations,
            "message": message,
            "contained": contained,
        }
        with self._lock:
            self.incidents.append(incident)
        return incident

    def set_robot_state(self, robot_id: str, **fields):
        with self._lock:
            self.robot_state.setdefault(robot_id, {})
            self.robot_state[robot_id].update(fields)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "revoked_jtis": sorted(self.revoked_jtis),
                "quarantined_identities": sorted(self.quarantined_identities),
                "incidents": list(self.incidents),
                "robot_state": dict(self.robot_state),
            }

    def reset(self):
        with self._lock:
            self.revoked_jtis.clear()
            self.quarantined_identities.clear()
            self.seen_command_ids.clear()
            self.command_timestamps.clear()
            self.incidents.clear()
            self.robot_state.clear()


state = OmniGuardState()
