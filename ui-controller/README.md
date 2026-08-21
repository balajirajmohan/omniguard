# OmniGuard controller UI

Two analog sticks, one robot. Both sticks send **real** commands; the only
difference is identity, and OmniGuard decides which one reaches the robot.

Vite + React + Tailwind v4.

```bash
cd ui-controller
npm install
npm run dev        # http://127.0.0.1:5173
```

Set the host under **Settings** (defaults to `http://localhost:8501`). Values are
stored per-browser in `localStorage`, so changing hosts needs no rebuild.

## How a stick becomes motion

| Step | Where | When |
|---|---|---|
| Authorize | `POST {api}/api/commands` | Target zone or speed band changes — **on change only, never on a timer** (see below) |
| Move | `POST {bridge}/move` | 8 Hz while authorized. Identical payload to the `curl` that already works |
| Stop | `POST {bridge}/stop` | On release, on block, and on deadman |

**The rogue panel is not blocked by JavaScript.** It sends the same command the
operator sends and gets `BLOCK` back because its `device_id` is
`rogue-controller`, which trips `UNKNOWN_DEVICE` — a hard violation in
`backend/policy.py`. If the UI simply refused to send, the demo would prove
nothing.

Verified against a live backend:

| Input | Result |
|---|---|
| Operator, any deflection | `ALLOW` (risk 0.19–0.29) |
| Rogue, same zone and speed | `BLOCK` `UNKNOWN_DEVICE` |
| Operator immediately after | `BLOCK` `REVOKED_CREDENTIAL` |
| Overspeed toggle | `BLOCK` `EXCESSIVE_SPEED` |
| Steering up into the restricted zone | `BLOCK` `RESTRICTED_DESTINATION` |

## Why the stick maps to 0.45–1.05 m/s, not 0–1.5

`backend/anomaly.py` trains its IsolationForest on speeds drawn from
`uniform(0.3, 1.2)`. Anything below ~0.4 or at/above ~1.15 scores as
out-of-distribution, risk climbs past 0.60, and `decide()` returns `HOLD`. Map
the stick to the full 0–1.5 governor range and the **legitimate** operator gets
held at both a light touch and full deflection, and the robot never moves.

Measured risk across 0.45–1.05 is 0.22–0.29, comfortably inside `ALLOW`. The
constants live at the top of `src/lib/omniguard.js`. Widen them only after
retraining the detector on the real teleop range.

## Other things worth knowing

- **Bridge calls use `mode:'no-cors'`.** `isaac/command_bridge.py` sends no CORS
  headers and has no `OPTIONS` handler, so a normal JSON POST would fail
  preflight. A bodied POST with the default `text/plain` type is a simple
  request: it is delivered, and `json.loads` parses it server-side because the
  bridge reads raw bytes without checking Content-Type. The response is opaque,
  which costs nothing — verdicts come from the API, which does send CORS headers.
- **Position is dead-reckoned.** The bridge has no pose readback, so the map
  integrates commanded motion rather than ground truth. Reset re-syncs to the
  origin. Add `GET /state` to the bridge and this becomes real.
- **Containment is global by design.** When the attacker is blocked, the shared
  credential is revoked, so the operator's stick stops working too. That is the
  point — press **Reset demo** to rotate it.
- **Gamepad needs a secure context.** `navigator.getGamepads()` is hidden over
  plain http on a bare IP. `npm run dev` binds `127.0.0.1`, which *is* a secure
  context, so a real DualSense works: left stick drives the operator, right
  stick the attacker.
- **Reset drives home through the policy engine** (`/api/reset`, then an
  authorized command to `SAFE_ZONE_A`) rather than poking the bridge, so the
  return trip is itself an authorized move.

## Attack toggles (rogue panel)

- **Overspeed** — ignores the 1.5 m/s governor, so a command that would
  otherwise be in-policy also trips `EXCESSIVE_SPEED`.
- **Bypass broker** — skips `:8000` and drives `:8899` directly. The robot moves
  and nothing stops it. This is the live argument for keeping port 8899 closed
  to everything except the GPU host itself.

## Geometry

Zone rectangles live in one block in `src/lib/omniguard.js`, anchored on the
waypoints in `backend/actuation.py` (`SAFE_ZONE_A` 0,0 · `SAFE_ZONE_B` 10,4 ·
`RESTRICTED_ZONE` 6,8). The two safe rectangles are adjacent at `x=5` so there
is a continuous drivable strip; a gap would block the robot mid-route.
Restricted is matched first so overlaps fail closed.

Driving right or left stays in policy. Driving **up** (`y > 5`) enters
`RESTRICTED_ZONE` and is blocked even for the legitimate operator. Retune once
real extents are read off the Isaac stage.

## Layout

```text
src/
├── App.jsx                    layout + revocation banner
├── lib/omniguard.js           transport, zone geometry, measured constants
├── lib/useController.js       8 Hz loop, authorization, dead reckoning, deadman
└── components/                Joystick, ControlPanel, WarehouseMap, TopBar, ...
```


---

# Backend v0.3.0 — three findings that affect the demo

Measured against `origin/main`'s backend, not inferred.

## 1. `/api/commands` now rejects the old payload

`CommandRequest` is `extra="forbid"` and no longer accepts
`commands_last_10_seconds` or `previous_failures` — they are derived server-side
by `backend/behavior.py`. Sending them returns
`422 Extra inputs are not permitted`. `buildCommand` was fixed accordingly.

## 2. Sustained teleop through the policy path cannot stay ALLOW

The retrained model (`iforest-v1`, 7 features) scores against server-derived
timing. Measured on a single, entirely legitimate command:

| Feature | Effect |
|---|---|
| `hour_of_day` outside ~09:00–17:00 | risk **0.62 → HOLD**, regardless of anything else |
| `seconds_since_last_command` ≤ 5 s | risk **0.60 → HOLD** |
| `speed` outside 0.6–1.0 m/s | 0.81–0.83 → **BLOCK** |
| `commands_last_10_seconds` | barely matters (0.30–0.48 across 0–80) |

Live, at one command every 2.5 s, the operator escalates:
`HOLD 0.62 → HOLD 0.73 → HOLD 0.74 → BLOCK 0.81`.

So the UI now authorizes **once per grab, per zone — never on a timer**, which is
the fewest commands the policy path can be asked for. It does not fix the
underlying issue: any repeated command inside 5 s is held, and outside business
hours the first one already is. Resolving it needs a backend change (a teleop
session concept, or dropping hour/gap for manual control) — out of scope here.

**Scenario runs are unaffected** — they inject a `BehaviorContext` override and
produce clean verdicts, which is why the scenario panel is the reliable demo path.

## 3. The bridge cannot be reached from a browser once auth is on

`isaac/command_bridge.py` now requires `X-OmniGuard-Bridge-Token` whenever it is
bound off-loopback or a token is set, and it still sends **no CORS headers and
has no `OPTIONS` handler**. A custom header is forbidden in `mode:'no-cors'` and
would force a preflight the bridge cannot answer — so browser-driven motion works
**only** while the bridge runs on loopback with no token set.

If you need the joystick with auth enabled, the bridge needs an `OPTIONS` handler
plus `Access-Control-Allow-Origin` / `-Headers`, or the motion call has to be
proxied through the backend.
