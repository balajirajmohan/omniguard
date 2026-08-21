import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import requests

logger = logging.getLogger("omniguard.robot_adapter")


class RobotController(ABC):
    @abstractmethod
    def move_to(self, robot_id: str, x: float, y: float, speed: float) -> bool:
        ...

    @abstractmethod
    def emergency_stop(self, robot_id: str) -> bool:
        ...


class MockRobotController(RobotController):
    def __init__(self):
        self._positions: dict[str, tuple[float, float]] = {}

    def move_to(self, robot_id: str, x: float, y: float, speed: float) -> bool:
        self._positions[robot_id] = (x, y)
        logger.info(
            "[MOCK] robot=%s moving to (%.2f, %.2f) at speed=%.2f",
            robot_id,
            x,
            y,
            speed,
        )
        return True

    def emergency_stop(self, robot_id: str) -> bool:
        logger.warning("[MOCK] robot=%s EMERGENCY STOP", robot_id)
        return True


class IsaacRobotController(RobotController):
    def __init__(self, base_url: str | None = None, timeout: float = 3.0):
        self.base_url = (
            base_url or os.environ.get("ISAAC_BRIDGE_URL", "http://127.0.0.1:8899")
        ).rstrip("/")
        self.timeout = timeout
        self.token = os.environ.get("ISAAC_BRIDGE_TOKEN", "omniguard-bridge")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-OmniGuard-Bridge-Token": self.token,
        }

    def _post_queued(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = requests.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            if resp.status_code == 401:
                return {"ok": False, "error": "unauthorized"}
            resp.raise_for_status()
            body = resp.json()
            return {
                "ok": True,
                "command_id": body.get("command_id"),
                "status": body.get("status", "QUEUED"),
            }
        except requests.RequestException as exc:
            logger.exception("Isaac bridge request failed path=%s payload=%s", path, payload)
            return {"ok": False, "error": str(exc)}

    def move_to_queued(
        self, robot_id: str, x: float, y: float, speed: float
    ) -> dict[str, Any]:
        return self._post_queued(
            "/move", {"robot_id": robot_id, "x": x, "y": y, "speed": speed}
        )

    def arm_preset_queued(self, robot_id: str, preset: str) -> dict[str, Any]:
        return self._post_queued(
            "/arm/preset", {"robot_id": robot_id, "preset": preset}
        )

    def arm_joints_queued(
        self, robot_id: str, targets_degrees: dict[str, float]
    ) -> dict[str, Any]:
        return self._post_queued(
            "/arm/joints",
            {"robot_id": robot_id, "targets_degrees": targets_degrees},
        )

    def gripper_queued(self, robot_id: str, action: str) -> dict[str, Any]:
        return self._post_queued(
            "/gripper", {"robot_id": robot_id, "action": action}
        )

    def emergency_stop_queued(self, robot_id: str) -> dict[str, Any]:
        return self._post_queued("/stop", {"robot_id": robot_id})

    def get_command_status(self, command_id: str) -> str | None:
        try:
            resp = requests.get(
                f"{self.base_url}/commands/{command_id}",
                headers=self._headers(),
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None
            return resp.json().get("status")
        except requests.RequestException:
            return None

    def get_state(self) -> dict[str, Any] | None:
        try:
            resp = requests.get(
                f"{self.base_url}/state",
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return None

    def move_to(self, robot_id: str, x: float, y: float, speed: float) -> bool:
        return bool(self.move_to_queued(robot_id, x, y, speed).get("ok"))

    def emergency_stop(self, robot_id: str) -> bool:
        return bool(self.emergency_stop_queued(robot_id).get("ok"))


def get_robot_controller() -> RobotController:
    backend = os.environ.get("OMNIGUARD_ROBOT_BACKEND", "mock").lower()
    if backend == "isaac":
        return IsaacRobotController()
    return MockRobotController()
