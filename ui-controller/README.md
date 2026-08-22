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

## Layout

Two views, switched from the top bar.

**Console** is viewport-locked on desktop (`xl:h-dvh`) so nothing important sits
below the fold. The hero is the warehouse floor beside the DualSense; the map
fills whatever height it is given rather than dictating page height, and each
card scrolls internally instead of growing the page. Scenarios, latest decision
and the investigator sit in a fixed rail under the hero.

**Logs** keeps every run. A session is archived automatically when **Reset demo**
is pressed — the backend wipes its state, which used to destroy the evidence of
the run you had just demonstrated. Sessions persist in `localStorage` (bounded to
25, best-effort), and the in-flight run is listed as a first-class session so
nothing is invisible before the first reset.

Exports: **Decisions CSV** and **Session JSON** per session, plus **All** for
every archived session. CSV quotes every field and doubles embedded quotes, so
free-text reasons cannot break the column count.

## Control surface

The DualSense is drawn in SVG and is a real control surface, not decoration:

| Input | Operator (left stick) | Hacker (right stick) |
|---|---|---|
| Pointer | drag the left stick | drag the right stick |
| Keyboard | **W A S D** | **arrow keys** |
| Gamepad | left stick | right stick |

The light bars either side of the touchpad carry each plane's live verdict.

### Arm, gripper and stop are on the buttons

Every button is live on screen *and* on a physical pad (standard mapping):

| Button | Command | Endpoint |
|---|---|---|
| D-pad ↑ / ↓ / ← / → | arm `reach` / `stow` / `carry` / `inspect` (lease holder) | `POST /api/teleop/arm/preset` |
| L1 / L2 | operator gripper `open` / `close` | `POST /api/teleop/gripper` |
| R1 / R2 | hacker gripper `open` / `close` | `POST /api/teleop/gripper` |
| Circle | emergency stop — ends every active lease | `POST /api/teleop/stop` |

Preset and action names mirror the sets `backend/teleop.py` validates against;
anything else returns `INVALID_ARM_PRESET` / `INVALID_GRIPPER_ACTION`. A test
pins the button map to those sets so a rename cannot silently start failing.

Arm presets ride whichever plane currently holds a **movement lease** (shown under
the sticks). Gripper shoulders are always plane-addressed (left = operator, right
= hacker). With no lease yet, the UI takes a short **aux lease** via
`/api/teleop/start` at the robot's current pose so the press still produces a real
identity/policy verdict — a hacker gripper press is blocked by the backend, not by
an inert button. A rejection tears that lease down exactly like a rejected
movement packet.

Physical buttons fire on the rising edge only, so holding one does not stream
commands.

### Keyboard needs no focus

The listener is on `window`, not on the stick element, so nothing has to be
clicked first — that was the old behaviour and it was discoverable only by
accident. The keys are split across the two planes rather than sharing one
focused control, so both can be driven at once. Typing in Settings is unaffected
(`input`, `textarea`, `select` and `contenteditable` are ignored), arrows are
prevented from scrolling the page, and a held key is released on blur so it
cannot latch a direction.

Diagonals are normalised, so `W`+`D` is not faster than `W`.

## Gamepad

Works over USB or Bluetooth. A DualSense reports `mapping: "standard"`, so:

| Control | Does |
|---|---|
| Left stick | Drives the **operator** plane |
| Right stick | Drives the **rogue** plane |
| L1 / L2 | Operator gripper open / close |
| R1 / R2 | Hacker gripper open / close |
| D-pad | Arm presets for the current lease holder |
| Circle | Emergency stop — ends every active lease via `/api/teleop/stop` |

Two things to know:

- **`navigator.getGamepads()` requires a secure context.** `npm run dev` binds
  `127.0.0.1`, which qualifies. Opening the same page over plain http on a LAN IP
  hides the Gamepad API entirely and the label says so.
- **Chrome exposes nothing until the pad sends input.** Plugging in is not enough
  — press any button once. The status label reads
  `press any button to connect` rather than the misleading "none connected".

The pad is sampled on `requestAnimationFrame` (display rate) and written straight
to the thumb's transform, so stick motion is smooth and causes no React
re-renders. Movement is still *sent* at the backend's `stream_hz`. Sampling on
the send tick is what used to make it feel stepped.

Releasing a physical stick publishes an explicit zero, so the on-screen thumb
springs back. Publishing `null` on release was the bug that left it stuck at full
deflection while control had already stopped.

Non-standard mappings are detected and flagged in the label rather than silently
reading the wrong axes.

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
