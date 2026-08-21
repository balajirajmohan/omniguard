# Wire Isaac after Checkpoint D (fake robot) is green

1. Prove move/stop in Isaac Python (no network).
2. Implement TODOs in [`simulator/isaac_bridge.py`](../simulator/isaac_bridge.py).
3. Point `OMNIGUARD_API_URL` at the broker (`http://<laptop-ip>:8000` or localhost on the GPU box).
4. Stop `simulator/fake_robot.py` so only Isaac polls `/api/robots/robot-01/next-command`.
5. Telemetry must POST `status=CONTAINED` and `speed=0` on STOP so the dashboard reflects truth.

Optional: use helpers under [`isaac/`](../isaac/) for an in-process HTTP bridge if you prefer push from the broker instead of poll. For the event, prefer the poll contract — it matches the starter kit and runbook.
