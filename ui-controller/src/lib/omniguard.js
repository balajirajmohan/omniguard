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

const REQUEST_TIMEOUT_MS = 15_000;

async function request(cfg, method, path, body, extraHeaders) {
  let res;
  const headers = {...(extraHeaders || {})};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  /* Timeout for reads — mutating requests must not be silently aborted. */
  const ac = method === "GET" ? new AbortController() : null;
  const timer = ac ? setTimeout(() => ac.abort(), REQUEST_TIMEOUT_MS) : null;
  try {
    res = await fetch(cfg.api + path, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ac?.signal,
    });
  } catch (err) {
    throw new ApiError(`network: ${err.message}`, {status: 0});
  } finally {
    if (timer) clearTimeout(timer);
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

/* ============================================================= AI ENDPOINTS
 * Consume the backend AI response engine. These endpoints may return 404 when
 * the AI branch has not been merged; callers must degrade gracefully.
 * Mutating endpoints (investigate, feedback, recover) are never auto-retried.
 * All mutation endpoints send X-OmniGuard-Operator header for authorization. */

const operatorHeaders = (cfg) => {
  const token = cfg?.operatorToken || DEMO_OPERATOR_TOKEN;
  return token ? { [OPERATOR_HEADER]: token } : {};
};

export const getAiStatus = (cfg) => apiGet(cfg, "/api/ai/status");
export const listIncidents = (cfg) => apiGet(cfg, "/api/incidents");
export const getIncident = (cfg, id) =>
  apiGet(cfg, `/api/incidents/${encodeURIComponent(id)}`);
export const investigateIncident = (cfg, id) =>
  apiPost(cfg, `/api/incidents/${encodeURIComponent(id)}/investigate`, undefined, operatorHeaders(cfg));
export const submitIncidentFeedback = (cfg, id, body) =>
  apiPost(cfg, `/api/incidents/${encodeURIComponent(id)}/feedback`, body, operatorHeaders(cfg));
export const advanceIncidentRecovery = (cfg, id, body) =>
  apiPost(cfg, `/api/incidents/${encodeURIComponent(id)}/recover`, body, operatorHeaders(cfg));

/* ======================================================== NORMALIZATION
 * Pure helpers that shape backend responses into the forms components expect.
 * Every field is nullable; nothing is fabricated. These never compute
 * authoritative scores, never label anomaly scores as probabilities, and
 * never display model_confidence when the backend sends null. */

const str = (v) => (typeof v === "string" && v ? v : null);
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const arr = (v) => (Array.isArray(v) ? v : []);
const bool = (v) => (v === true || v === false ? v : null);
const iso = (v) => {
  if (!v) return null;
  try { return new Date(v).toISOString(); } catch { return null; }
};

export function normalizeAiStatus(raw) {
  if (!raw || typeof raw !== "object") {
    return {
      available: false, model_version: null, degraded: null,
      artifact_verified: null, policy_version: null, ai_mode: null,
    };
  }
  const s = raw.command_anomaly ?? raw.action_window_anomaly ?? raw;
  return {
    available: s.available !== false,
    model_version: str(s.model_version ?? raw.model_version),
    degraded: bool(s.degraded ?? raw.degraded),
    artifact_verified: bool(s.artifact_verified ?? raw.artifact_verified),
    policy_version: str(s.policy_version ?? raw.policy_version),
    ai_mode: str(s.ai_mode ?? raw.ai_mode),
  };
}

/** Decision-source values from backend main commit 65737e3.
 * Never heuristically replace a backend-provided decision_source. */
const DECISION_SOURCES = [
  "hard_policy",
  "action_window_ai",
  "behavioral_rule",
  "hybrid_rule_ml",
  "ai_warning",
  "deterministic_fallback",
  "none",
];

export function classifyDecisionSource(event) {
  if (!event) return null;
  const rawSrc = str(event.decision_source) ?? str(event.ai_evidence?.decision_source);
  if (rawSrc) {
    const srcLower = rawSrc.toLowerCase();
    if (DECISION_SOURCES.includes(srcLower)) return srcLower;
    return rawSrc;
  }
  const hpWouldBlock = bool(event.hard_policy?.would_block) ?? bool(event.hard_policy_would_block) ?? bool(event.ai_evidence?.hard_policy_would_block);
  if (hpWouldBlock === true) {
    return "hard_policy";
  }
  if (hpWouldBlock === false && event.final_decision !== "ALLOW") {
    return "action_window_ai";
  }
  return null;
}

export function normalizeDecisionIntelligence(event) {
  if (!event || typeof event !== "object") return null;
  const ev = event.ai_evidence ?? {};
  const hp = event.hard_policy ?? ev.hard_policy ?? {};
  const holdStop = ev.hold_stop ?? event.hold_stop ?? event;

  const hpWouldBlock = bool(hp.would_block) ?? bool(ev.hard_policy_would_block) ?? bool(event.hard_policy_would_block);
  const hpReasons = arr(hp.reasons ?? ev.hard_policy_reasons ?? event.hard_policy_reasons);

  return {
    decision_source: classifyDecisionSource(event),
    final_decision: str(event.final_decision),
    hard_policy_would_block: hpWouldBlock,
    hard_policy_reasons: hpReasons,
    anomaly_risk_score: num(ev.anomaly_risk_score) ?? num(event.anomaly_risk_score),
    behavioral_rule_score: num(ev.behavioral_rule_score) ?? num(event.behavioral_rule_score),
    effective_risk: num(ev.effective_risk) ?? num(event.effective_risk),
    anomaly_model: str(ev.anomaly_model) ?? str(event.anomaly_model),
    anomaly_model_version: str(ev.model_version) ?? str(event.anomaly_model_version),
    anomaly_features:
      (ev.anomaly_features && typeof ev.anomaly_features === "object" ? ev.anomaly_features : null) ??
      (event.anomaly_features && typeof event.anomaly_features === "object" ? event.anomaly_features : null),
    ai_mode: str(ev.ai_mode) ?? str(event.ai_mode),
    /* model_confidence: null stays null — never rendered as 0% or N/A. */
    model_confidence: num(ev.model_confidence) ?? num(event.model_confidence),
    incident_id: str(event.incident_id),
    response_playbook: str(event.response_playbook) ?? str(event.playbook),
    artifact_verified: bool(ev.artifact_verified) ?? bool(event.artifact_verified),
    model_degraded: bool(ev.model_degraded) ?? bool(event.model_degraded),
    policy_version: str(ev.policy_version) ?? str(event.policy_version),

    /* Physical-stop truth fields from hold_stop */
    stop_requested: bool(holdStop.stop_requested ?? event.stop_requested),
    stop_request_accepted: bool(holdStop.stop_request_accepted ?? event.stop_request_accepted),
    stop_confirmed: bool(holdStop.stop_confirmed ?? event.stop_confirmed),
    robot_stopped: bool(holdStop.stop_confirmed ?? event.stop_confirmed), // NEVER true unless stop_confirmed === true
    stop_stage: str(holdStop.stop_stage ?? event.stop_stage),
    stop_ack: str(holdStop.stop_ack ?? event.stop_ack),

    /* Presentation flags derived from the normalized shape, not policy. */
    credential_status: str(event.credential_status),
    device_status: str(event.device_status),
    zone_status: str(event.zone_status),
    caught_by: str(event.caught_by),
  };
}

export function normalizeIncidentSummary(raw) {
  if (!raw || typeof raw !== "object") return null;
  const aiEv = raw.ai_evidence ?? {};
  return {
    incident_id: str(raw.incident_id) ?? str(raw.id),
    status: str(raw.status),
    first_seen: iso(raw.first_event_at) ?? iso(raw.first_seen),
    last_seen: iso(raw.last_event_at) ?? iso(raw.last_seen),
    event_count: num(raw.event_count) ?? num(raw.count),
    agent_id: str(raw.agent_id),
    device_id: str(raw.device_id),
    robot_id: str(raw.robot_id),
    demo_run_id: str(raw.demo_run_id),
    decision_source: str(raw.decision_source) ?? str(aiEv.decision_source),
    anomaly_risk_score: num(aiEv.anomaly_risk_score) ?? num(raw.anomaly_risk_score) ?? num(raw.risk),
    behavioral_rule_score: num(aiEv.behavioral_rule_score) ?? num(raw.behavioral_rule_score),
    effective_risk: num(aiEv.effective_risk) ?? num(raw.effective_risk),
    response_playbook: str(raw.playbook) ?? str(raw.response_playbook),
    containment_status: str(raw.containment?.status) ?? str(raw.containment_status),
    model_version: str(raw.model_version) ?? str(aiEv.model_version),
    policy_version: str(raw.policy_version) ?? str(aiEv.policy_version),
    raw: raw,
  };
}

export function normalizeIncidentDetail(raw) {
  if (!raw || typeof raw !== "object") return null;
  const summary = normalizeIncidentSummary(raw);
  const llmExpl = raw.llm_explanation ?? raw.explanation ?? raw.incident_explanation ?? null;
  return {
    ...summary,
    /* Section 1: Executive summary */
    executive_summary:
      str(llmExpl?.summary) ?? str(llmExpl?.operator_summary) ?? str(raw.executive_summary) ?? str(raw.summary),
    /* Section 2: Technical evidence */
    technical_evidence: raw.technical_evidence ?? raw.ai_evidence?.anomaly_features ?? null,
    /* Section 3: Identity and device */
    identity: raw.identity ?? (raw.agent_id || raw.device_id ? { agent_id: raw.agent_id, device_id: raw.device_id } : null),
    /* Section 4: Action sequence */
    action_sequence: arr(raw.action_sequence),
    /* Section 5: Robot and zone context */
    robot_context: raw.robot_context ?? (raw.robot_id ? { robot_id: raw.robot_id } : null),
    /* Section 6: AI model evidence */
    ai_evidence: raw.ai_evidence ?? null,
    /* Section 7: Hard-policy evidence */
    hard_policy: raw.hard_policy ?? raw.hard_policy_evidence ?? null,
    /* Section 8: Containment actions */
    containment: raw.containment ?? null,
    /* Section 9: Isaac acknowledgements */
    isaac_acks: arr(
      raw.containment?.bridge_acknowledgements ??
        raw.containment?.acknowledgements ??
        raw.isaac_acks ??
        raw.isaac_acknowledgements
    ),
    /* Section 10: Agent investigation */
    agent_trace: raw.agent_trace ?? raw.investigation ?? null,
    /* Section 11: LLM explanation + provenance */
    llm_explanation: llmExpl,
    /* Section 12: Feedback */
    human_feedback: raw.human_feedback ?? raw.feedback ?? null,
    /* Section 13: Recovery */
    recovery: raw.recovery ?? null,
    /* Event correlation */
    correlated_events: arr(raw.correlated_events ?? raw.events),
    common_reason: str(raw.common_reason),
    affected_robots: arr(raw.affected_robots),
    affected_identities: arr(raw.affected_identities),
  };
}

export function normalizeAgentTrace(raw) {
  if (!raw || typeof raw !== "object") return null;
  const rawSteps = arr(raw.tool_trace ?? raw.steps ?? raw.tool_calls);
  const steps = rawSteps.map((s) => ({
    tool: str(s.tool) ?? str(s.tool_name) ?? str(s.name),
    timestamp: iso(s.at ?? s.timestamp ?? s.start_time ?? s.started_at),
    start_time: iso(s.start_time ?? s.at ?? s.timestamp ?? s.started_at),
    end_time: iso(s.end_time ?? s.completed_at),
    result: str(s.result ?? s.result_summary ?? s.summary),
    result_summary: str(s.result_summary ?? s.result ?? s.summary),
    ok: s.ok !== false && !s.error,
    error: str(s.error),
  }));
  return {
    agent_mode: str(raw.agent_mode ?? raw.mode),
    provider: str(raw.provider),
    model: str(raw.model),
    fallback_used: raw.fallback_used === true || raw.is_fallback === true,
    tools_used: arr(raw.tools_used),
    proposed_playbook: str(raw.proposed_playbook ?? raw.playbook),
    /* Critical: proposed !== executed. Containment must confirm execution. */
    execution_authorized: raw.execution_authorized === true,
    steps,
  };
}

export function normalizeLlmProvenance(raw) {
  if (!raw || typeof raw !== "object") {
    return {
      status: "unavailable", provider: null, model: null,
      fallback_used: false, fallback_reason: null,
      summary: null, technical_summary: null,
      physical_impact: null, root_cause: null, why_suspicious: null,
      containment_taken: null, recommended_actions: [],
      generated_at: null, latency_ms: null,
    };
  }
  const fallback = raw.fallback_used === true || raw.is_fallback === true;
  let status = "live_llm";
  if (raw.status === "pending" || raw.pending) status = "pending";
  else if (raw.status === "failed" || raw.error) status = "failed";
  else if (fallback) status = "deterministic_fallback";
  else if (!raw.provider && !raw.model) status = "unavailable";

  const whySusp = Array.isArray(raw.why_suspicious) ? raw.why_suspicious.join(', ') : str(raw.why_suspicious);
  const contTaken = Array.isArray(raw.containment_taken) ? raw.containment_taken.join(', ') : str(raw.containment_taken);

  return {
    status,
    provider: str(raw.provider),
    model: str(raw.model),
    fallback_used: fallback,
    fallback_reason: str(raw.fallback_reason),
    summary: str(raw.summary ?? raw.operator_summary),
    technical_summary: str(raw.technical_summary),
    physical_impact: str(raw.physical_impact),
    root_cause: str(raw.root_cause ?? raw.likely_root_cause),
    why_suspicious: whySusp,
    containment_taken: contTaken,
    recommended_actions: arr(raw.recommended_actions),
    generated_at: iso(raw.generated_at),
    latency_ms: num(raw.latency_ms ?? raw.latency),
  };
}

export function normalizeRecoveryState(raw) {
  if (!raw || typeof raw !== "object") return null;
  return {
    state: str(raw.state),
    label: str(raw.label),
    simulated: raw.simulated === true,
    evidence: raw.evidence && typeof raw.evidence === "object" ? raw.evidence : {},
    history: arr(raw.history),
    idp_workflow_complete: raw.idp_workflow_complete === true,
    runtime_access_restored: raw.runtime_access_restored === true,
    can_advance: raw.can_advance === true,
  };
}
