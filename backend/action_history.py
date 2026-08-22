"""Thread-safe bounded rolling action history for teleop/AI windows."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from backend.action_context import ActionContext, ActionType

MOVE_TYPES = {ActionType.BASE_MOVE}
ARM_TYPES = {ActionType.ARM_PRESET, ActionType.ARM_JOINTS}
GRIPPER_TYPES = {ActionType.GRIPPER_OPEN, ActionType.GRIPPER_CLOSE}


class ActionHistory:
    def __init__(self, *, maxlen: int = 2000) -> None:
        self._lock = threading.RLock()
        self._events: deque[ActionContext] = deque(maxlen=maxlen)
        self._failures: dict[str, int] = {}
        self._seen_arm: set[str] = set()
        self._seen_gripper: set[str] = set()

    def reset_demo_state(self) -> None:
        with self._lock:
            self._events.clear()
            self._failures.clear()
            self._seen_arm.clear()
            self._seen_gripper.clear()

    def record(self, context: ActionContext) -> None:
        with self._lock:
            self._events.append(context)
            key = f"{context.agent_id}|{context.device_id}"
            if context.action_type in ARM_TYPES:
                self._seen_arm.add(key)
            if context.action_type in GRIPPER_TYPES:
                self._seen_gripper.add(key)

    def note_failure(self, agent_id: str, device_id: str) -> None:
        with self._lock:
            key = f"{agent_id}|{device_id}"
            self._failures[key] = self._failures.get(key, 0) + 1

    def recent_for_session(self, session_id: str | None, seconds: float) -> list[ActionContext]:
        if not session_id:
            return []
        return self._recent(lambda c: c.session_id == session_id, seconds)

    def recent_for_identity(self, agent_id: str, seconds: float) -> list[ActionContext]:
        return self._recent(lambda c: c.agent_id == agent_id, seconds)

    def recent_for_robot(self, robot_id: str, seconds: float) -> list[ActionContext]:
        return self._recent(lambda c: c.robot_id == robot_id, seconds)

    def _recent(self, predicate, seconds: float) -> list[ActionContext]:
        cutoff = datetime.now(timezone.utc).timestamp() - seconds
        with self._lock:
            out: list[ActionContext] = []
            for ctx in self._events:
                try:
                    ts = datetime.fromisoformat(ctx.timestamp.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    continue
                if ts >= cutoff and predicate(ctx):
                    out.append(ctx)
            return out

    def summarize_window(self, context: ActionContext) -> dict[str, Any]:
        """Derive window features for the incoming action (includes the action conceptually)."""
        session_events = self.recent_for_session(context.session_id, 10.0)
        identity_events = self.recent_for_identity(context.agent_id, 10.0)
        events = session_events or identity_events
        # Include the prospective action in the window summary.
        synthetic = list(events) + [context]

        move_count = sum(1 for e in synthetic if e.action_type in MOVE_TYPES)
        arm_count = sum(1 for e in synthetic if e.action_type in ARM_TYPES)
        gripper_count = sum(1 for e in synthetic if e.action_type in GRIPPER_TYPES)

        switches = 0
        for i in range(1, len(synthetic)):
            if synthetic[i].action_type != synthetic[i - 1].action_type:
                switches += 1

        speeds: list[float] = []
        for e in synthetic:
            if e.action_type == ActionType.BASE_MOVE:
                speed = e.action_payload.get("speed")
                if isinstance(speed, (int, float)):
                    speeds.append(float(speed))

        zones: list[str] = []
        for e in self.recent_for_session(context.session_id, 60.0) or self.recent_for_identity(
            context.agent_id, 60.0
        ):
            if e.robot_zone:
                zones.append(e.robot_zone)
        if context.robot_zone:
            zones.append(context.robot_zone)
        zone_transitions = 0
        for i in range(1, len(zones)):
            if zones[i] != zones[i - 1]:
                zone_transitions += 1

        gripper_actions = [e for e in synthetic if e.action_type in GRIPPER_TYPES]
        gripper_toggles = 0
        for i in range(1, len(gripper_actions)):
            if gripper_actions[i].action_type != gripper_actions[i - 1].action_type:
                gripper_toggles += 1

        key = f"{context.agent_id}|{context.device_id}"
        with self._lock:
            previous_failures = self._failures.get(key, 0)
            first_arm = 1.0 if key not in self._seen_arm and context.action_type in ARM_TYPES else 0.0
            first_gripper = (
                1.0
                if key not in self._seen_gripper and context.action_type in GRIPPER_TYPES
                else 0.0
            )

        seconds_since = None
        if events:
            try:
                last = datetime.fromisoformat(events[-1].timestamp.replace("Z", "+00:00"))
                now = datetime.fromisoformat(context.timestamp.replace("Z", "+00:00"))
                seconds_since = max(0.0, (now - last).total_seconds())
            except ValueError:
                seconds_since = None

        return {
            "commands_last_10_seconds": len(synthetic),
            "move_actions_last_10_seconds": move_count,
            "arm_actions_last_10_seconds": arm_count,
            "gripper_actions_last_10_seconds": gripper_count,
            "action_type_switches_last_10_seconds": switches,
            "zone_transitions_last_60_seconds": zone_transitions,
            "previous_failures": previous_failures,
            "seconds_since_last_action": seconds_since,
            "hour_of_day": context.hour_of_day,
            "move_count_10s": float(move_count),
            "arm_count_10s": float(arm_count),
            "gripper_count_10s": float(gripper_count),
            "action_switch_count_10s": float(switches),
            "maximum_speed": float(max(speeds) if speeds else 0.0),
            "average_speed": float(sum(speeds) / len(speeds) if speeds else 0.0),
            "zone_transition_count": float(zone_transitions),
            "gripper_toggle_count": float(gripper_toggles),
            "first_arm_use_for_identity": first_arm,
            "first_gripper_use_for_identity": first_gripper,
        }


action_history = ActionHistory()
