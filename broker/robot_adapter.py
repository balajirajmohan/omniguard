import logging
import os
from abc import ABC, abstractmethod

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
    """Simulates robot movement without Isaac Sim.

    Lets the broker, policy engine and dashboard be built and demoed on any
    machine, independent of Isaac Sim/GPU availability. Swap for
    IsaacRobotController once the Isaac Sim bridge is reachable.
    """

    def __init__(self):
        self._positions: dict[str, tuple[float, float]] = {}

    def move_to(self, robot_id: str, x: float, y: float, speed: float) -> bool:
        self._positions[robot_id] = (x, y)
        logger.info("[MOCK] robot=%s moving to (%.2f, %.2f) at speed=%.2f", robot_id, x, y, speed)
        return True

    def emergency_stop(self, robot_id: str) -> bool:
        logger.warning("[MOCK] robot=%s EMERGENCY STOP", robot_id)
        return True


class IsaacRobotController(RobotController):
    """Forwards approved commands to the Isaac Sim command bridge.

    The bridge (isaac/command_bridge.py) runs inside Isaac Sim's own Python
    process on the GPU host, since Isaac's robot APIs are only importable
    there. This class just does the HTTP call from wherever the broker runs.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 3.0):
        self.base_url = (base_url or os.environ.get("ISAAC_BRIDGE_URL", "http://localhost:8899")).rstrip("/")
        self.timeout = timeout

    def move_to(self, robot_id: str, x: float, y: float, speed: float) -> bool:
        try:
            resp = requests.post(
                f"{self.base_url}/move",
                json={"robot_id": robot_id, "x": x, "y": y, "speed": speed},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException:
            logger.exception("Isaac bridge move_to failed for robot=%s", robot_id)
            return False

    def emergency_stop(self, robot_id: str) -> bool:
        try:
            resp = requests.post(
                f"{self.base_url}/stop",
                json={"robot_id": robot_id},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException:
            logger.exception("Isaac bridge emergency_stop failed for robot=%s", robot_id)
            return False


def get_robot_controller() -> RobotController:
    backend = os.environ.get("OMNIGUARD_ROBOT_BACKEND", "mock").lower()
    if backend == "isaac":
        return IsaacRobotController()
    return MockRobotController()
