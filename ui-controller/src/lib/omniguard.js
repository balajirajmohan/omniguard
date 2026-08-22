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
  api: "http://127.0.0.1:8000",
  robot: "robot-01",
};

/* The fleet credential and demo operator token are deliberately NOT persisted —
 * they stay in memory for the life of the tab. Writing either to localStorage
 * would leave working secrets in the browser profile after the demo. */
export const DEMO_CREDENTIAL = "fleet-agent-valid-token";
/** Matches backend OMNIGUARD_OPERATOR_TOKEN — required only for Protection OFF. */
export const DEMO_OPERATOR_TOKEN = "omniguard-operator";
export const OPERATOR_HEADER = "X-OmniGuard-Operator";

export function loadConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem("omniguard.cfg") || "{}");
    delete saved.credential; // ignore anything a previous build persisted
    delete saved.operatorToken;
    delete saved.bridge; // the bridge is not addressable from a browser
    return {
      ...DEFAULTS,
      ...saved,
      credential: DEMO_CREDENTIAL,
      operatorToken: DEMO_OPERATOR_TOKEN,
    };
  } catch {
    return {
      ...DEFAULTS,
      credential: DEMO_CREDENTIAL,
      operatorToken: DEMO_OPERATOR_TOKEN,
    };
  }
}

export function saveConfig(cfg) {
  try {
    const {credential, operatorToken, ...persistable} = cfg;
    localStorage.setItem("omniguard.cfg", JSON.stringify(persistable));
  } catch {
    /* private mode */
  }
}

export const IDENTITIES = {
  legit: {agent_id: "fleet-agent-01", device_id: "fleet-controller-01"},
  rogue: {agent_id: "fleet-agent-01", device_id: "rogue-controller"},
};

export const DEADZONE = 0.12;

/* Standard gamepad mapping. A DualSense reports mapping "standard" over both USB
 * and Bluetooth, so panel 0 (operator) takes the left stick and panel 1
 * (attacker) the right. Circle is the physical emergency stop. */
export const PAD_ESTOP_BUTTON = 1;

/** Pure axis read, so the mapping is testable without a browser or hardware. */
export function padStickFor(pad, panelIndex, deadzone = DEADZONE) {
  const x = pad?.axes?.[panelIndex * 2] ?? 0;
  const y = -(pad?.axes?.[panelIndex * 2 + 1] ?? 0);
  const raw = Math.hypot(x, y);
  if (!Number.isFinite(raw) || raw <= deadzone) {
    return {vec: {x: 0, y: 0}, mag: 0, active: false};
  }
  return {vec: {x, y}, mag: Math.min(1, raw), active: true};
}

export const padEstopPressed = (pad) =>
  pad?.buttons?.[PAD_ESTOP_BUTTON]?.pressed === true;
export const LOOKAHEAD = 2.5; // metres ahead of the robot the setpoint sits

/* Mirrors GET /api/teleop/config exactly. Used ONLY when the gateway is not
 * reachable yet (backend branch not merged), and the UI says so plainly rather
 * than pretending it has authoritative geometry. */
export const FALLBACK_TELEOP_CONFIG = {
  robot_id: "robot-01",
  max_speed: 1.5,
  stream_hz: 8,
  deadman_timeout_ms: 750,
  lease_ttl_seconds: 30,
  zones: {
    SAFE_ZONE_A: {x_min: -4, x_max: 4, y_min: -4, y_max: 2},
    SAFE_ZONE_B: {x_min: 4, x_max: 12, y_min: -4, y_max: 2},
    RESTRICTED_ZONE: {x_min: 2, x_max: 10, y_min: 2.5, y_max: 7.5},
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
  const inside = ([, r]) =>
    x >= r.x_min && x <= r.x_max && y >= r.y_min && y <= r.y_max;
  const hit = entries.filter(inside);
  if (!hit.length) return "OUT_OF_BOUNDS";
  return (hit.find(([n]) => isRestrictedZone(n)) ?? hit[0])[0]; // restricted wins
}

/** Centre waypoint for autonomous duties. The backend still classifies every
 * coordinate; this helper only chooses a point safely inside the advertised
 * rectangle and never supplies a trusted zone name to a movement request. */
export function zoneCenter(zones, name) {
  const rect = zones?.[name];
  if (!rect) return null;
  return {
    x: (rect.x_min + rect.x_max) / 2,
    y: (rect.y_min + rect.y_max) / 2,
  };
}

/** Clockwise patrol points inset from a rectangular zone boundary. The inset is
 * deliberate: exact edges are legal today, but leaving clearance makes the duty
 * robust to footprint/collision tolerances in the physical twin. */
export function zonePerimeter(zones, name, inset = 0.75) {
  const rect = zones?.[name];
  const values = rect
    ? [rect.x_min, rect.x_max, rect.y_min, rect.y_max, inset]
    : [];
  if (
    values.length !== 5 ||
    values.some((value) => !Number.isFinite(value)) ||
    inset <= 0 ||
    rect.x_max - rect.x_min <= inset * 2 ||
    rect.y_max - rect.y_min <= inset * 2
  ) {
    return null;
  }
  const left = rect.x_min + inset;
  const right = rect.x_max - inset;
  const bottom = rect.y_min + inset;
  const top = rect.y_max - inset;
  return [
    {id: "south-west", label: "south-west corner", x: left, y: bottom},
    {id: "south-east", label: "south-east corner", x: right, y: bottom},
    {id: "north-east", label: "north-east corner", x: right, y: top},
    {id: "north-west", label: "north-west corner", x: left, y: top},
  ];
}

/** Route descriptions used by the background duty scheduler. Unknown scenarios
 * fail closed, and all coordinates come from backend-advertised geometry. */
export function simulationRoute(zones, scenario) {
  if (scenario === "zone-shuttle") {
    const a = zoneCenter(zones, "SAFE_ZONE_A");
    const b = zoneCenter(zones, "SAFE_ZONE_B");
    return a && b
      ? [
          {id: "SAFE_ZONE_A", label: "Zone A", ...a},
          {id: "SAFE_ZONE_B", label: "Zone B", ...b},
        ]
      : null;
  }
  if (scenario === "zone-a-perimeter") {
    return zonePerimeter(zones, "SAFE_ZONE_A");
  }
  return null;
}

export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Stick deflection -> commanded speed. Deterministic policy caps at max_speed. */
export function speedFor(mag, {maxSpeed, overspeed = false} = {}) {
  if (mag <= DEADZONE) return 0;
  /* A modified client is not bound by the vendor's governor — this is what makes
   * the overspeed attack real rather than simulated. */
  if (overspeed) return +(maxSpeed + 2).toFixed(2);
  const t = Math.min(1, (mag - DEADZONE) / (1 - DEADZONE));
  return +Math.max(0.1, t * maxSpeed).toFixed(2);
}

/* --------------------------------------------------------------- transport */

export class ApiError extends Error {
  constructor(message, {status, body} = {}) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request(cfg, method, path, body, extraHeaders) {
  let res;
  const headers = {...(extraHeaders || {})};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  try {
    res = await fetch(cfg.api + path, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    throw new ApiError(`network: ${err.message}`, {status: 0});
  }
  const text = await res.text();
  let parsed = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON */
  }
  if (!res.ok) {
    const detail = parsed?.detail ?? parsed?.reason ?? res.statusText;
    throw new ApiError(
      typeof detail === "string" ? detail : `HTTP ${res.status}`,
      {status: res.status, body: parsed},
    );
  }
  return parsed;
}

export const apiGet = (cfg, path) => request(cfg, "GET", path);
const apiPost = (cfg, path, body, extraHeaders) =>
  request(cfg, "POST", path, body, extraHeaders);

/** Backend move/start rejects use `reasons[]`; older shapes used a singular `reason`. */
export function rejectionReasons(resOrBody) {
  if (!resOrBody || typeof resOrBody !== "object") return [];
  if (Array.isArray(resOrBody.reasons) && resOrBody.reasons.length) {
    return resOrBody.reasons.map(String);
  }
  if (resOrBody.reason != null && resOrBody.reason !== "") {
    return [String(resOrBody.reason)];
  }
  if (Array.isArray(resOrBody.detail)) {
    return resOrBody.detail.map((d) =>
      typeof d === "string" ? d : (d?.msg ?? JSON.stringify(d)),
    );
  }
  if (typeof resOrBody.detail === "string" && resOrBody.detail) {
    return [resOrBody.detail];
  }
  if (
    resOrBody.status &&
    !["EXECUTED", "QUEUED", "ALLOW"].includes(resOrBody.status)
  ) {
    return [String(resOrBody.status)];
  }
  return [];
}

/* ------------------------------------------------------- read endpoints */

export const getHealth = (cfg) => apiGet(cfg, "/health");
export const getState = (cfg) => apiGet(cfg, "/api/state");
export const getEvents = (cfg) => apiGet(cfg, "/api/events");
export const getTimeline = (cfg) => apiGet(cfg, "/api/timeline");
export const getLatestIncident = (cfg) => apiGet(cfg, "/api/incidents/latest");
export const listScenarios = (cfg) => apiGet(cfg, "/api/scenarios");
export const investigate = (cfg) => apiPost(cfg, "/api/investigate");
export const resetBackend = (cfg) => apiPost(cfg, "/api/reset");

/**
 * Run a named scenario. Protection OFF is a judge/demo comparison only and
 * requires the in-memory operator token — never persisted, never optional when
 * protection=false (backend returns 401 without X-OmniGuard-Operator).
 */
export const runScenario = (
  cfg,
  id,
  {protection = true, resetFirst = true} = {},
) => {
  const headers = {};
  if (!protection) {
    headers[OPERATOR_HEADER] = cfg.operatorToken || DEMO_OPERATOR_TOKEN;
  }
  return apiPost(
    cfg,
    `/api/scenarios/${encodeURIComponent(id)}/run` +
      `?protection=${protection}&reset_first=${resetFirst}`,
    undefined,
    headers,
  );
};

/* --------------------------------------------- teleoperation gateway ---
 * Frozen contract. Field names and shapes are fixed by agreement with the
 * backend; do not rename them locally. */

export const getTeleopConfig = (cfg) => apiGet(cfg, "/api/teleop/config");

export const teleopStart = (cfg, panelId, {x, y, speed}) =>
  apiPost(cfg, "/api/teleop/start", {
    credential: cfg.credential,
    ...IDENTITIES[panelId],
    robot_id: cfg.robot,
    x: +x.toFixed(3),
    y: +y.toFixed(3),
    speed: +speed.toFixed(2),
  });

export const teleopMove = (cfg, {controlId, sequence, x, y, speed}) =>
  apiPost(cfg, "/api/teleop/move", {
    control_id: controlId,
    sequence,
    robot_id: cfg.robot,
    x: +x.toFixed(3),
    y: +y.toFixed(3),
    speed: +speed.toFixed(2),
    /* No zone field on purpose — the backend derives it. A browser-supplied
     * zone name would be attacker-controlled input to a safety check. */
  });

export const teleopStop = (cfg, {controlId, reason}) =>
  apiPost(cfg, "/api/teleop/stop", {
    control_id: controlId,
    robot_id: cfg.robot,
    reason,
  });

export const teleopArmPreset = (cfg, {controlId, preset}) =>
  apiPost(cfg, "/api/teleop/arm/preset", {
    control_id: controlId,
    robot_id: cfg.robot,
    preset,
  });

export const teleopArmJoints = (cfg, {controlId, targetsDegrees}) =>
  apiPost(cfg, "/api/teleop/arm/joints", {
    control_id: controlId,
    robot_id: cfg.robot,
    targets_degrees: targetsDegrees,
  });

export const teleopGripper = (cfg, {controlId, action}) =>
  apiPost(cfg, "/api/teleop/gripper", {
    control_id: controlId,
    robot_id: cfg.robot,
    action,
  });

/* ------------------------------------------------------------ presentation */

export const RISK_WARNING = 0.6;
export const RISK_CRITICAL = 0.8;
export const riskBand = (r) =>
  r >= RISK_CRITICAL ? "critical" : r >= RISK_WARNING ? "warning" : "normal";

export const FEATURE_LABELS = {
  speed: "speed",
  known_device: "known device",
  restricted_destination: "restricted target",
  commands_last_10_seconds: "commands / 10s",
  previous_failures: "prior failures",
  hour_of_day: "hour of day",
  seconds_since_last_command: "gap since last",
};

/** Normalises isaac_bridge_state.position, which may arrive as [x,y] or {x,y}. */
export function readPosition(bridgeState) {
  const p = bridgeState?.position;
  if (!p) return null;
  const x = Array.isArray(p) ? p[0] : p.x;
  const y = Array.isArray(p) ? p[1] : p.y;
  return Number.isFinite(x) && Number.isFinite(y) ? {x, y} : null;
}

/* --------------------------------------------------------------- manipulator
 * Arm and gripper state has two very different sources, and the map must not
 * confuse them:
 *
 *   confirmed  isaac_bridge_state.arm / .gripper. The bridge only grows these
 *              keys once Isaac has actually executed the command
 *              (isaac/warehouse_robot_demo.py -> bridge.mark_executed), so they
 *              are ground truth -- but they are absent before the first
 *              command, and absent forever in mock mode, because
 *              backend/main.py's mock_bridge_state has no arm/gripper fields
 *              and nothing ever adds them.
 *   commanded  what this UI last got an EXECUTED/QUEUED response for. The only
 *              thing available in mock mode, and honest only if labelled.
 *
 * Confirmed always wins; commanded is the fallback; nothing is invented. */
export const ARM_PRESETS = ["stow", "carry", "reach", "inspect"];
export const GRIPPER_ACTIONS = ["open", "close"];

/* Forward extension per preset, 0 (tucked) .. 1 (fully reaching), read off
 * ARM_PRESETS_DEGREES in isaac/warehouse_robot_demo.py. Display only -- the
 * real arm is a 7-DOF Franka; this is its top-down projection. */
export const ARM_EXTENSION = {stow: 0.3, carry: 0.52, reach: 1, inspect: 0.74};
/* Only "inspect" swings the base joint off-centre (panda_joint1 = +25 deg). */
export const ARM_YAW_DEGREES = {stow: 0, carry: 0, reach: 0, inspect: 25};

export function readManipulator(bridgeState, commanded = {}) {
  const armState = bridgeState?.arm;
  const gripperState = bridgeState?.gripper;

  let arm = null;
  if (armState?.mode === "preset" && ARM_PRESETS.includes(armState.preset)) {
    arm = {preset: armState.preset, mode: "preset", source: "confirmed"};
  } else if (armState?.mode === "joints") {
    /* Explicit joint targets have no preset name; the map draws a neutral pose
     * rather than pretending it knows which preset this resembles. */
    arm = {preset: null, mode: "joints", source: "confirmed"};
  } else if (ARM_PRESETS.includes(commanded.arm)) {
    arm = {preset: commanded.arm, mode: "preset", source: "commanded"};
  }

  let gripper = null;
  if (GRIPPER_ACTIONS.includes(gripperState?.action)) {
    gripper = {action: gripperState.action, source: "confirmed"};
  } else if (GRIPPER_ACTIONS.includes(commanded.gripper)) {
    gripper = {action: commanded.gripper, source: "commanded"};
  }

  return arm || gripper ? {arm, gripper} : null;
}

/* The bridge reports no yaw, so facing is derived from motion evidence: the
 * active target first, then the last trail segment. Falls back to +x so the
 * arm still renders when the robot has never moved. */
export function headingFrom(robot, target, trail) {
  if (robot && target) {
    const dx = target.x - robot.x;
    const dy = target.y - robot.y;
    if (Math.hypot(dx, dy) > 0.05) return Math.atan2(dy, dx);
  }
  if (trail?.length > 1) {
    const b = trail[trail.length - 1];
    const a = trail[trail.length - 2];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    if (Math.hypot(dx, dy) > 0.05) return Math.atan2(dy, dx);
  }
  return 0;
}
