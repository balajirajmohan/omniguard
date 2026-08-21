"""HTTP bridge that lets the OmniGuard broker drive a robot inside Isaac Sim.

Runs INSIDE the Isaac Sim process on the GPU host (import it from your
standalone script, after SimulationApp has started). Uses only the stdlib
HTTP server so it never needs pip installs inside Isaac Sim's Python env.

Commands arrive over HTTP on a background thread and are handed to the main
simulation loop via a thread-safe dict, since Isaac Sim's physics/render step
must stay on the main thread.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class CommandBridge:
    def __init__(self, host: str = "0.0.0.0", port: int = 8899):
        self._lock = threading.Lock()
        self._moves: dict[str, dict] = {}
        self._stops: set[str] = set()
        self._server = ThreadingHTTPServer((host, port), self._make_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

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

            def do_GET(self):
                if self.path == "/health":
                    self._reply(200, {"status": "ok", "service": "omniguard-isaac-bridge"})
                else:
                    self._reply(404, {"error": "not found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                try:
                    data = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    self._reply(400, {"error": "invalid json"})
                    return

                if self.path == "/move":
                    robot_id = data.get("robot_id")
                    if not robot_id:
                        self._reply(400, {"error": "robot_id required"})
                        return
                    with bridge._lock:
                        bridge._moves[robot_id] = {
                            "x": data["x"],
                            "y": data["y"],
                            "speed": data["speed"],
                        }
                        bridge._stops.discard(robot_id)
                    self._reply(200, {"status": "queued"})
                elif self.path == "/stop":
                    robot_id = data.get("robot_id")
                    if not robot_id:
                        self._reply(400, {"error": "robot_id required"})
                        return
                    with bridge._lock:
                        bridge._stops.add(robot_id)
                        bridge._moves.pop(robot_id, None)
                    self._reply(200, {"status": "stopping"})
                else:
                    self._reply(404, {"error": "not found"})

            def log_message(self, fmt, *args):
                pass  # keep Isaac Sim's console output clean

        return Handler

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()

    def pop_move(self, robot_id: str) -> dict | None:
        with self._lock:
            return self._moves.pop(robot_id, None)

    def pop_stop(self, robot_id: str) -> bool:
        with self._lock:
            if robot_id in self._stops:
                self._stops.discard(robot_id)
                return True
            return False
