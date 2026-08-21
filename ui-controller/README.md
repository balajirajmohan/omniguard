# OmniGuard controller UI

The interactive command center. Two analog sticks, one robot, one security
boundary. Vite + React + Tailwind v4.

```bash
cd ui-controller
npm ci
npm run dev      # http://127.0.0.1:5173
npm test         # 16 tests
npm run build
```

## Security boundary

```text
React UI  ->  OmniGuard backend :8000  ->  secured bridge :8899  ->  Isaac Sim
```

The browser talks to the backend and **nothing else**. It holds no bridge token,
never calls `:8899`, and cannot actuate the robot directly. This is enforced by a
test that scans shipped source for the bridge port and by a grep over the
production bundle.

Both control planes send **real** requests. The rogue panel is not blocked in
JavaScript — it sends the same payload with `device_id: rogue-controller` and the
backend rejects it. A client-side block would prove nothing.

## Teleoperation contract

Frozen by agreement with the backend. Do not rename fields locally.

| Call | When |
|---|---|
| `GET /api/teleop/config` | Once on load. Authoritative zones, `max_speed`, `stream_hz`, `deadman_timeout_ms`, `lease_ttl_seconds` |
| `POST /api/teleop/start` | First deflection past the deadzone. Returns a short-lived constrained lease |
| `POST /api/teleop/move` | At `stream_hz` while held. Monotonic `sequence`, **no browser-supplied zone** |
| `POST /api/teleop/stop` | Centre, pointer release/cancel, key release, gamepad deadzone, blur, page hide, unmount, any rejection |

AI scores the **session**, not the packet. The lease strip on each panel shows
`control_id`, `max_speed` and `allowed_zones`; the badge shows the backend's
`enforcement_mode` (expected `SHADOW_TELEOP`) alongside its risk score.

Every movement packet still gets deterministic checks server-side. Any rejection
fails closed: streaming stops, `/api/teleop/stop` is called, and the structured
reason is shown.

## Position is never invented

Pose comes from `GET /api/state` → `isaac_bridge_state` — `position`, `target`,
`speed`, `motion_state`, `last_command_id`. **Dead reckoning has been removed.**
If the backend has not reported a pose, the map says
`awaiting isaac_bridge_state.position` rather than drawing a robot at the origin.

Polling is ~350 ms while a lease is streaming and 1.5 s when idle.

**Reset** clears security state and stops any session. It does **not** move the
robot or reset the map to `(0,0)` — the next poll shows wherever Isaac actually
left it.

## Credential handling

The fleet credential is held in memory for the tab and is **never written to
localStorage**. `loadConfig()` also strips any `credential` or `bridge` left
behind by an earlier build. Neither is editable in Settings.

## What each panel shows

- Verdict lamp with icon and word (never colour alone), lease strip, AI mode badge
- `anomaly_risk_score` against the 0.60 / 0.80 thresholds, `caught_by`,
  `hard_policy_would_block`, policy decision, containment acknowledgement
- Server-derived behavioural features, so a HOLD can be explained not just asserted
- Scenario panel (`/api/scenarios`), decision trace (`/api/timeline`),
  investigator (`/api/investigate`), incident (`/api/incidents/latest`)

Protection ON/OFF lives **only** in the scenario panel, never on the joysticks.

The AI-only scenario visibly shows `hard_policy_would_block: false`,
`caught_by: ai_anomaly`, `final_decision: BLOCK` — rules would have allowed it.

## Degradation

If `/api/teleop/config` 404s (gateway branch not merged), the UI shows a banner
saying so, marks the zone geometry as contract defaults rather than
server-authoritative, and keeps scenarios, telemetry and investigation working.
Joystick authorization then reports `TELEOP_GATEWAY_NOT_DEPLOYED` instead of
failing silently.

## Input

Pointer drag, arrow keys or WASD while focused, and a real gamepad — left stick
drives the operator, right stick the attacker. `navigator.getGamepads()` needs a
secure context, which `127.0.0.1` provides.

## Layout

```text
src/
├── App.jsx                    layout, banners
├── lib/omniguard.js           API client, frozen contract, zone helpers
├── lib/useController.js       lease lifecycle, streaming, deadman, polling
├── lib/__tests__/             16 tests incl. the :8899 boundary scan
└── components/                Joystick, ControlPanel, WarehouseMap,
                               ScenarioPanel, DecisionCard, RiskMeter,
                               InvestigatePanel, TelemetryRail, TopBar
```
