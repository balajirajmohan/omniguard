/* OmniGuard API client.
 *
 * SECURITY BOUNDARY: the browser talks to the OmniGuard backend and nothing
 * else. It never contacts the Isaac bridge on :8899, never holds the bridge
 * token, and never actuates the robot directly. Movement reaches Isaac only as:
 *
 *   React UI  ->  backend :8000  ->  secured bridge :8899  ->  Isaac
 *
 * The rogue control plane is NOT blocked in this file, or anywhere in the UI.
 * It sends the same request the operator sends, with a different device_id, and
 * the backend rejects it. A client-side block would prove nothing.
 */

export const DEFAULTS = {
  api: 'http://127.0.0.1:8000',
  robot: 'robot-01',
};

/* The fleet credential is deliberately NOT persisted — it stays in memory for
 * the life of the tab. Writing it to localStorage would leave a working robot
 * credential sitting in the browser profile after the demo. */
export const DEMO_CREDENTIAL = 'fleet-agent-valid-token';

export function loadConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem('omniguard.cfg') || '{}');
    delete saved.credential;   // ignore anything a previous build persisted
    delete saved.bridge;       // the bridge is not addressable from a browser
    return { ...DEFAULTS, ...saved, credential: DEMO_CREDENTIAL };
  } catch {
    return { ...DEFAULTS, credential: DEMO_CREDENTIAL };
  }
}

export function saveConfig(cfg) {
  try {
    const { credential, ...persistable } = cfg;   // credential intentionally dropped
    localStorage.setItem('omniguard.cfg', JSON.stringify(persistable));
  } catch { /* private mode */ }
}

export const IDENTITIES = {
  legit: { agent_id: 'fleet-agent-01', device_id: 'fleet-controller-01' },
  rogue: { agent_id: 'fleet-agent-01', device_id: 'rogue-controller' },
};

export const DEADZONE = 0.12;
export const LOOKAHEAD = 2.5;   // metres ahead of the robot the setpoint sits

/* Mirrors GET /api/teleop/config exactly. Used ONLY when the gateway is not
 * reachable yet (backend branch not merged), and the UI says so plainly rather
 * than pretending it has authoritative geometry. */
export const FALLBACK_TELEOP_CONFIG = {
  robot_id: 'robot-01',
  max_speed: 1.5,
  stream_hz: 8,
  deadman_timeout_ms: 750,
  lease_ttl_seconds: 30,
  zones: {
    SAFE_ZONE_A: { x_min: -5, x_max: 5, y_min: -5, y_max: 5 },
    SAFE_ZONE_B: { x_min: 5, x_max: 15, y_min: -5, y_max: 5 },
    RESTRICTED_ZONE: { x_min: 2, x_max: 12, y_min: 5, y_max: 12 },
  },
};

export const isRestrictedZone = (name) => /RESTRICTED|HUMAN/i.test(name);

/** Drawable extent, derived from whichever zone set is in force. */
export function floorBounds(zones) {
  const rects = Object.values(zones ?? {});
  if (!rects.length) return [-6, -6, 16, 13];
  const pad = 1;
  return [
    Math.min(...rects.map((r) => r.x_min)) - pad,
    Math.min(...rects.map((r) => r.y_min)) - pad,
    Math.max(...rects.map((r) => r.x_max)) + pad,
    Math.max(...rects.map((r) => r.y_max)) + pad,
  ];
}

/* DISPLAY ONLY. The backend computes the authoritative zone for every packet and
 * the UI never sends a zone name. This exists so the operator can see where a
 * setpoint is heading before the verdict comes back. */
export function zoneAt(x, y, zones) {
  const entries = Object.entries(zones ?? {});
  const inside = ([, r]) => x >= r.x_min && x <= r.x_max && y >= r.y_min && y <= r.y_max;
  const hit = entries.filter(inside);
  if (!hit.length) return 'OUT_OF_BOUNDS';
  return (hit.find(([n]) => isRestrictedZone(n)) ?? hit[0])[0];   // restricted wins
}

export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Stick deflection -> commanded speed. Deterministic policy caps at max_speed. */
export function speedFor(mag, { maxSpeed, overspeed = false } = {}) {
  if (mag <= DEADZONE) return 0;
  /* A modified client is not bound by the vendor's governor — this is what makes
   * the overspeed attack real rather than simulated. */
  if (overspeed) return +(maxSpeed + 2).toFixed(2);
  const t = Math.min(1, (mag - DEADZONE) / (1 - DEADZONE));
  return +Math.max(0.1, t * maxSpeed).toFixed(2);
}

/* --------------------------------------------------------------- transport */

export class ApiError extends Error {
  constructor(message, { status, body } = {}) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request(cfg, method, path, body) {
  let res;
  try {
    res = await fetch(cfg.api + path, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    throw new ApiError(`network: ${err.message}`, { status: 0 });
  }
  const text = await res.text();
  let parsed = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { /* non-JSON */ }
  if (!res.ok) {
    const detail = parsed?.detail ?? parsed?.reason ?? res.statusText;
    throw new ApiError(typeof detail === 'string' ? detail : `HTTP ${res.status}`,
      { status: res.status, body: parsed });
  }
  return parsed;
}

export const apiGet = (cfg, path) => request(cfg, 'GET', path);
const apiPost = (cfg, path, body) => request(cfg, 'POST', path, body);

/* ------------------------------------------------------- read endpoints */

export const getHealth         = (cfg) => apiGet(cfg, '/health');
export const getState          = (cfg) => apiGet(cfg, '/api/state');
export const getEvents         = (cfg) => apiGet(cfg, '/api/events');
export const getTimeline       = (cfg) => apiGet(cfg, '/api/timeline');
export const getLatestIncident = (cfg) => apiGet(cfg, '/api/incidents/latest');
export const listScenarios     = (cfg) => apiGet(cfg, '/api/scenarios');
export const investigate       = (cfg) => apiPost(cfg, '/api/investigate');
export const resetBackend      = (cfg) => apiPost(cfg, '/api/reset');

export const runScenario = (cfg, id, { protection = true, resetFirst = true } = {}) =>
  apiPost(cfg, `/api/scenarios/${encodeURIComponent(id)}/run` +
    `?protection=${protection}&reset_first=${resetFirst}`);

/* --------------------------------------------- teleoperation gateway ---
 * Frozen contract. Field names and shapes are fixed by agreement with the
 * backend; do not rename them locally. */

export const getTeleopConfig = (cfg) => apiGet(cfg, '/api/teleop/config');

export const teleopStart = (cfg, panelId, { x, y, speed }) =>
  apiPost(cfg, '/api/teleop/start', {
    credential: cfg.credential,
    ...IDENTITIES[panelId],
    robot_id: cfg.robot,
    x: +x.toFixed(3),
    y: +y.toFixed(3),
    speed: +speed.toFixed(2),
  });

export const teleopMove = (cfg, { controlId, sequence, x, y, speed }) =>
  apiPost(cfg, '/api/teleop/move', {
    control_id: controlId,
    sequence,
    robot_id: cfg.robot,
    x: +x.toFixed(3),
    y: +y.toFixed(3),
    speed: +speed.toFixed(2),
    /* No zone field on purpose — the backend derives it. A browser-supplied
     * zone name would be attacker-controlled input to a safety check. */
  });

export const teleopStop = (cfg, { controlId, reason }) =>
  apiPost(cfg, '/api/teleop/stop', {
    control_id: controlId,
    robot_id: cfg.robot,
    reason,
  });

/* ------------------------------------------------------------ presentation */

export const RISK_WARNING = 0.60;
export const RISK_CRITICAL = 0.80;
export const riskBand = (r) =>
  r >= RISK_CRITICAL ? 'critical' : r >= RISK_WARNING ? 'warning' : 'normal';

export const FEATURE_LABELS = {
  speed: 'speed',
  known_device: 'known device',
  restricted_destination: 'restricted target',
  commands_last_10_seconds: 'commands / 10s',
  previous_failures: 'prior failures',
  hour_of_day: 'hour of day',
  seconds_since_last_command: 'gap since last',
};

/** Normalises isaac_bridge_state.position, which may arrive as [x,y] or {x,y}. */
export function readPosition(bridgeState) {
  const p = bridgeState?.position;
  if (!p) return null;
  const x = Array.isArray(p) ? p[0] : p.x;
  const y = Array.isArray(p) ? p[1] : p.y;
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}
