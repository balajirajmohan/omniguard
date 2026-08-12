"""Isaac Sim control adapter.

In hackathon mode without Isaac running, this logs approved actions.
On the GPU workstation, replace `_send_to_isaac` with Isaac Python scripting
or ROS 2 bridge calls that actually move Nova Carter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from broker.models import MoveCommand
from broker.store import EventStore

logger = logging.getLogger("omniguard.isaac")


@dataclass
class AdapterResult:
    action: str
    detail: str
    simulated: bool = True


class IsaacAdapter:
    def __init__(self, store: EventStore, enabled: bool = False) -> None:
        self.store = store
        self.enabled = enabled

    def execute_move(self, command: MoveCommand) -> AdapterResult:
        detail = (
            f"Move {command.robot_id} → {command.destination_zone} "
            f"at {command.speed} m/s from {command.device_id}"
        )
        if self.enabled:
            self._send_to_isaac(command)
            simulated = False
            action = "ISAAC_MOVE"
        else:
            logger.info("[stub] %s", detail)
            simulated = True
            action = "STUB_MOVE"

        self.store.set_robot(
            zone=command.destination_zone,
            speed=command.speed,
            status="MOVING",
            last_command=detail,
        )
        return AdapterResult(action=action, detail=detail, simulated=simulated)

    def emergency_stop(self, robot_id: str, reason: str) -> AdapterResult:
        detail = f"E-STOP {robot_id}: {reason}"
        if self.enabled:
            self._send_estop_to_isaac(robot_id)
            simulated = False
            action = "ISAAC_ESTOP"
        else:
            logger.warning("[stub] %s", detail)
            simulated = True
            action = "STUB_ESTOP"

        self.store.emergency_stop()
        self.store.set_robot(
            zone=self.store.robot_zone,
            speed=0.0,
            status="CONTAINED",
            last_command=detail,
        )
        return AdapterResult(action=action, detail=detail, simulated=simulated)

    def _send_to_isaac(self, command: MoveCommand) -> None:
        # Placeholder for Isaac Sim Script Editor / extension hook.
        # Example: publish a target pose for Nova Carter in the warehouse USD.
        raise NotImplementedError(
            "Wire this to Isaac Sim Python API on the g6e workstation"
        )

    def _send_estop_to_isaac(self, robot_id: str) -> None:
        raise NotImplementedError(
            "Wire zero-velocity / emergency-stop to Isaac Sim on the g6e workstation"
        )
