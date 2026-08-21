/* OmniGuard transport + policy geometry.
 *
 * Deliberately framework-free: every constant here was measured against the
 * running backend, and none of it should drift because a component was
 * refactored.
 *
 *   authorization  ->  POST {api}/api/commands   (the real policy engine)
 *   motion         ->  POST {bridge}/move        (same payload as the curl)
 *   stop           ->  POST {bridge}/stop
 *
 * The rogue panel is NOT blocked in this file, or anywhere else in the UI. It
 * sends the same command the operator sends and gets BLOCK back from the
 * broker because its device_id is not the enrolled controller. Enforcing the
 * block client-side would prove nothing.
 */

export const DEFAULTS = {
  api: 'http://localhost:8501',
  bridge: 'http://localhost:8899',
  credential: 'fleet-agent-valid-token',
  robot: 'robot-01',
};

export function loadConfig() {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem('omniguard.cfg') || '{}') };
  } catch {
    return { ...DEFAULTS };
  }
}
export function saveConfig(cfg) {
  try { localStorage.setItem('omniguard.cfg', JSON.stringify(cfg)); } catch { /* private mode */ }
}

export const POLICY_MAX_SPEED = 1.5; // backend/policy.py MAX_SPEED — the governor

/* The stick maps into 0.45-1.05 m/s, NOT 0-1.5, and that is deliberate.
 * backend/anomaly.py trains its IsolationForest on speeds drawn from
 * uniform(0.3, 1.2), so anything below ~0.4 or at/above ~1.15 scores as
 * out-of-distribution: risk climbs past 0.60 and decide() returns HOLD. A
 * legitimate operator would then be held at BOTH a light touch and full
 * deflection, and the robot would never move. Measured risk across this band
 * is 0.22-0.29, comfortably inside ALLOW.
 *
 * Widen only after retraining the detector on the real teleop range. */
export const STICK_MIN = 0.45;
export const STICK_MAX = 1.05;
export const OVERSPEED = 3.5;  // what a modified client would send
export const LOOKAHEAD = 2.5;  // metres ahead of the robot the setpoint sits
export const DEADZONE = 0.12;
export const TICK_MS = 125;    // 8 Hz motion streaming
export const REAUTH_MS = 2500; // re-check authorization even when nothing changed

/* Zone geometry, anchored on the waypoints in backend/actuation.py
 * (SAFE_ZONE_A 0,0 / SAFE_ZONE_B 10,4 / RESTRICTED_ZONE 6,8).
 * The safe rectangles are adjacent at x=5 so there is a continuous drivable
 * strip — a gap between them would block the robot mid-route. Restricted is
 * matched first so any overlap fails closed. Retune once real extents are
 * read off the Isaac stage; this block is the only geometry in the UI. */
export const RESTRICTED = { RESTRICTED_ZONE: [2, 5, 12, 12] };
export const SAFE = { SAFE_ZONE_A: [-5, -5, 5, 5], SAFE_ZONE_B: [5, -5, 15, 5] };
export const FLOOR = [-6, -6, 16, 13];

const inRect = ([x0, y0, x1, y1], x, y) => x >= x0 && x <= x1 && y >= y0 && y <= y1;

export function zoneAt(x, y) {
  for (const [n, r] of Object.entries(RESTRICTED)) if (inRect(r, x, y)) return n;
  for (const [n, r] of Object.entries(SAFE)) if (inRect(r, x, y)) return n;
  return 'OUT_OF_BOUNDS';
}

export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export const IDENTITIES = {
  legit: { agent_id: 'fleet-agent-01', device_id: 'fleet-controller-01' },
  rogue: { agent_id: 'fleet-agent-01', device_id: 'rogue-controller' },
};

/* ------------------------------------------------------------- transport */

async function apiPost(cfg, path, body) {
  const r = await fetch(cfg.api + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function apiGet(cfg, path) {
  const r = await fetch(cfg.api + path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/* No headers on purpose. isaac/command_bridge.py sends no CORS headers and has
 * no OPTIONS handler, so adding Content-Type: application/json would force a
 * preflight it cannot answer. A bodied POST with the default text/plain type is
 * a "simple request": it is delivered, and json.loads() parses it server-side
 * because the bridge reads raw bytes without checking Content-Type. We cannot
 * read the response, which costs nothing — verdicts come from the API. */
function bridgePost(cfg, path, body) {
  return fetch(cfg.bridge + path, {
    method: 'POST',
    mode: 'no-cors',
    body: JSON.stringify(body),
  }).catch(() => {});
}

export const sendMove = (cfg, x, y, speed) =>
  bridgePost(cfg, '/move', {
    robot_id: cfg.robot,
    x: +x.toFixed(3),
    y: +y.toFixed(3),
    speed: +speed.toFixed(3),
  });

export const sendStop = (cfg) => bridgePost(cfg, '/stop', { robot_id: cfg.robot });

export async function bridgeReachable(cfg) {
  try { await fetch(cfg.bridge + '/health', { mode: 'no-cors' }); return true; }
  catch { return false; }
}

/* v0.3.0 CommandRequest is `extra="forbid"`. Sending commands_last_10_seconds or
 * previous_failures — as this UI used to — now returns 422 "Extra inputs are not
 * permitted". Behavioural history is derived server-side by backend/behavior.py
 * from the request's own timing, and must not be supplied. */
export function buildCommand(cfg, panelId, zone, speed) {
  return {
    credential: cfg.credential,
    ...IDENTITIES[panelId],
    robot_id: cfg.robot,
    destination: zone,
    speed: +speed.toFixed(2),
    protection_enabled: true,
  };
}

export const authorize = (cfg, panelId, zone, speed) =>
  apiPost(cfg, '/api/commands', buildCommand(cfg, panelId, zone, speed));

export const resetBackend = (cfg) => apiPost(cfg, '/api/reset');

/* Drive home through the policy engine rather than poking the bridge, so the
 * return trip is itself an authorized command. */
export const driveHome = (cfg) =>
  apiPost(cfg, '/api/commands', buildCommand(cfg, 'legit', 'SAFE_ZONE_A', 1.0));

export function speedFor(mag, { overspeed = false } = {}) {
  if (mag <= DEADZONE) return 0;
  if (overspeed) return OVERSPEED;
  const t = Math.min(1, (mag - DEADZONE) / (1 - DEADZONE));
  return STICK_MIN + t * (STICK_MAX - STICK_MIN);
}

/* ------------------------------------------------- v0.3.0 read endpoints */

export const getHealth        = (cfg) => apiGet(cfg, '/health');
export const getState         = (cfg) => apiGet(cfg, '/api/state');
export const getEvents        = (cfg) => apiGet(cfg, '/api/events');
export const getTimeline      = (cfg) => apiGet(cfg, '/api/timeline');
export const getLatestIncident = (cfg) => apiGet(cfg, '/api/incidents/latest');
export const listScenarios    = (cfg) => apiGet(cfg, '/api/scenarios');

/* The agent is read-only by construction: it reports `disallowed:
 * ["arbitrary_robot_movement"]`, which is worth showing rather than hiding. */
export const investigate = (cfg) => apiPost(cfg, '/api/investigate');

export const runScenario = (cfg, id, { protection = true, resetFirst = true } = {}) =>
  apiPost(cfg, `/api/scenarios/${encodeURIComponent(id)}/run` +
    `?protection=${protection}&reset_first=${resetFirst}`);

export const runDemoNormal  = (cfg) => apiPost(cfg, '/api/demo/normal');
export const runDemoAnomaly = (cfg) => apiPost(cfg, '/api/demo/anomaly');
export const runDemoAttack  = (cfg, protection = true) =>
  apiPost(cfg, `/api/demo/attack?protection=${protection}`);

export const RISK_WARNING  = 0.60;
export const RISK_CRITICAL = 0.80;

export const riskBand = (r) =>
  r >= RISK_CRITICAL ? 'critical' : r >= RISK_WARNING ? 'warning' : 'normal';

/* Human labels for the server-derived feature vector, so a HOLD can be
 * explained instead of just asserted. */
export const FEATURE_LABELS = {
  speed: 'speed',
  known_device: 'known device',
  restricted_destination: 'restricted target',
  commands_last_10_seconds: 'commands / 10s',
  previous_failures: 'prior failures',
  hour_of_day: 'hour of day',
  seconds_since_last_command: 'gap since last',
};
