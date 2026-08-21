"""Isaac HTTP command bridge — auth, validation, and execution ack.

Runs inside the Isaac Sim process. Uses stdlib only.
"""

from __future__ import annotations

import hmac
import json
import math
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


MAX_BODY_BYTES = 4096
MAX_COORD = 1000.0
MAX_SPEED = 5.0
MIN_SPEED = 0.0


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


class CommandBridge:
    def __init__(
        self,
        host: str | None = None,
        port: int = 8899,
        token: str | None = None,
    ):
        self.host = host if host is not None else os.getenv(
            "ISAAC_BRIDGE_HOST", "127.0.0.1"
        )
        # Allow port=0 for ephemeral test binds; env used only when constructing defaults.
        if port == 8899 and os.getenv("ISAAC_BRIDGE_PORT"):
            self.port = int(os.getenv("ISAAC_BRIDGE_PORT", "8899"))
        else:
            self.port = int(port)
        self.token = token if token is not None else os.getenv(
            "ISAAC_BRIDGE_TOKEN", "omniguard-bridge"
        )
        self.require_auth = (not _is_loopback(self.host)) or bool(
            os.getenv("ISAAC_BRIDGE_REQUIRE_AUTH", "1") not in {"0", "false", "no"}
        )

        self._lock = threading.Lock()
        self._moves: dict[str, dict] = {}
        self._stops: set[str] = set()
        self._commands: dict[str, dict[str, Any]] = {}
        self._robot_state: dict[str, Any] = {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "target": None,
            "speed": 0.0,
            "motion_state": "IDLE",
            "last_command_id": None,
        }
        self._server = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def _authorized(self, handler: BaseHTTPRequestHandler) -> bool:
        if not self.require_auth:
            return True
        provided = handler.headers.get("X-OmniGuard-Bridge-Token", "")
        expected = self.token or ""
        if not expected:
            return False
        return hmac.compare_digest(provided.encode(), expected.encode())

    def _make_handler(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, code: int, body: dict):
                payload = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                if length < 0 or length > MAX_BODY_BYTES:
                    raise ValueError("request body too large")
                raw = self.rfile.read(length) if length else b"{}"
                data = json.loads(raw or b"{}")
                if not isinstance(data, dict):
                    raise ValueError("json object required")
                return data

            def do_GET(self):
                try:
                    parsed = urlparse(self.path)
                    path = parsed.path
                    if path == "/health":
                        self._reply(
                            200,
                            {
                                "status": "ok",
                                "service": "omniguard-isaac-bridge",
                                "auth_required": bridge.require_auth,
                                "bind": f"{bridge.host}:{bridge.port}",
                            },
                        )
                        return
                    if path == "/state":
                        if not bridge._authorized(self):
                            self._reply(401, {"error": "unauthorized"})
                            return
                        with bridge._lock:
                            self._reply(200, dict(bridge._robot_state))
                        return
                    if path.startswith("/commands/"):
                        if not bridge._authorized(self):
                            self._reply(401, {"error": "unauthorized"})
                            return
                        command_id = path.split("/", 2)[-1]
                        with bridge._lock:
                            cmd = bridge._commands.get(command_id)
                        if not cmd:
                            self._reply(404, {"error": "unknown command_id"})
                            return
                        self._reply(200, cmd)
                        return
                    self._reply(404, {"error": "not found"})
                except Exception as exc:  # noqa: BLE001
                    self._reply(500, {"error": "handler_error", "detail": str(exc)})

            def do_POST(self):
                try:
                    if not bridge._authorized(self):
                        self._reply(401, {"error": "unauthorized"})
                        return
                    data = self._read_json()
                    if self.path == "/move":
                        robot_id = data.get("robot_id")
                        if not isinstance(robot_id, str) or not robot_id.strip():
                            self._reply(400, {"error": "robot_id required"})
                            return
                        try:
                            x = _finite_number(data.get("x"), "x")
                            y = _finite_number(data.get("y"), "y")
                            speed = _finite_number(data.get("speed"), "speed")
                        except ValueError as exc:
                            self._reply(400, {"error": str(exc)})
                            return
                        if abs(x) > MAX_COORD or abs(y) > MAX_COORD:
                            self._reply(400, {"error": "coordinates out of range"})
                            return
                        if speed < MIN_SPEED or speed > MAX_SPEED:
                            self._reply(400, {"error": "speed out of range"})
                            return
                        command_id = str(uuid.uuid4())
                        with bridge._lock:
                            bridge._moves[robot_id] = {
                                "x": x,
                                "y": y,
                                "speed": speed,
                                "command_id": command_id,
                            }
                            bridge._stops.discard(robot_id)
                            bridge._commands[command_id] = {
                                "command_id": command_id,
                                "type": "move",
                                "robot_id": robot_id,
                                "status": "QUEUED",
                                "x": x,
                                "y": y,
                                "speed": speed,
                            }
                            bridge._robot_state["last_command_id"] = command_id
                        self._reply(
                            200,
                            {
                                "status": "QUEUED",
                                "command_id": command_id,
                            },
                        )
                    elif self.path == "/stop":
                        robot_id = data.get("robot_id")
                        if not isinstance(robot_id, str) or not robot_id.strip():
                            self._reply(400, {"error": "robot_id required"})
                            return
                        command_id = str(uuid.uuid4())
                        with bridge._lock:
                            bridge._stops.add(robot_id)
                            bridge._moves.pop(robot_id, None)
                            bridge._commands[command_id] = {
                                "command_id": command_id,
                                "type": "stop",
                                "robot_id": robot_id,
                                "status": "QUEUED",
                            }
                            bridge._robot_state["last_command_id"] = command_id
                        self._reply(
                            200,
                            {
                                "status": "QUEUED",
                                "command_id": command_id,
                            },
                        )
                    else:
                        self._reply(404, {"error": "not found"})
                except json.JSONDecodeError:
                    self._reply(400, {"error": "invalid json"})
                except ValueError as exc:
                    self._reply(400, {"error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    self._reply(500, {"error": "handler_error", "detail": str(exc)})

            def log_message(self, fmt, *args):
                pass

        return Handler

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()

    def pop_move(self, robot_id: str) -> dict | None:
        with self._lock:
            return self._moves.pop(robot_id, None)

    def pop_stop(self, robot_id: str) -> dict | None:
        """Return stop command payload if pending (prioritized by caller)."""
        with self._lock:
            if robot_id not in self._stops:
                return None
            self._stops.discard(robot_id)
            # Find latest queued stop for this robot
            command_id = None
            for cid, cmd in reversed(list(self._commands.items())):
                if (
                    cmd.get("robot_id") == robot_id
                    and cmd.get("type") == "stop"
                    and cmd.get("status") == "QUEUED"
                ):
                    command_id = cid
                    break
            return {"command_id": command_id, "robot_id": robot_id}

    def mark_executed(self, command_id: str | None, **state_updates: Any) -> None:
        if not command_id:
            return
        with self._lock:
            cmd = self._commands.get(command_id)
            if cmd:
                cmd["status"] = "EXECUTED"
            self._robot_state["last_command_id"] = command_id
            self._robot_state.update(state_updates)

    def mark_failed(self, command_id: str | None, reason: str = "failed") -> None:
        if not command_id:
            return
        with self._lock:
            cmd = self._commands.get(command_id)
            if cmd:
                cmd["status"] = "FAILED"
                cmd["reason"] = reason

    def update_state(self, **kwargs: Any) -> None:
        with self._lock:
            self._robot_state.update(kwargs)
