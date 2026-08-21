/**
 * All illustrative telemetry lives here so it can be replaced by real API
 * responses (see `src/config/endpoints.ts`) without touching any component.
 *
 * Values are demo telemetry, not measured production results.
 */

export type Outcome = 'ALLOW' | 'ALLOW_CONSTRAINED' | 'DENY' | 'ESTOP';

export type ScenarioId = 'normal' | 'stolen' | 'anomaly' | 'sensor';

export interface TraceStage {
  /** Short label shown in the decision trace. */
  label: string;
  /** Mono detail line rendered under the label. */
  detail: string;
  status: 'pass' | 'warn' | 'fail' | 'info';
}

export interface Field {
  key: string;
  value: string;
  status?: 'pass' | 'warn' | 'fail' | 'info';
}

/**
 * A policy reason carries its own verdict. Never infer it from the label —
 * `ZONE_PERMITTED` and `ZONE_NOT_PERMITTED` share a substring but are opposites.
 */
export interface PolicyReason {
  code: string;
  status: 'pass' | 'warn' | 'fail';
}

export interface Scenario {
  id: ScenarioId;
  name: string;
  /** One-line framing of what the operator is looking at. */
  blurb: string;
  command: string;
  fields: Field[];
  policyReasons: PolicyReason[];
  aiRisk: number;
  outcome: Outcome;
  outcomeLabel: string;
  /** Optional supporting narrative shown beneath the verdict. */
  note?: string;
  containment: string[];
  latencyMs: number;
  stages: TraceStage[];
}

export const POLICY_VERSION = 'v1.4';

export const scenarios: Scenario[] = [
  {
    id: 'normal',
    name: 'Normal Operation',
    blurb: 'A routine transport task from a bound controller inside a permitted zone.',
    command: 'MOVE → ZONE_B • 0.8 m/s',
    fields: [
      { key: 'identity', value: 'fleet-agent-01', status: 'pass' },
      { key: 'device', value: 'controller-01', status: 'pass' },
      { key: 'robot', value: 'robot-01', status: 'pass' },
      { key: 'destination', value: 'ZONE_B', status: 'pass' },
      { key: 'speed', value: '0.8 m/s', status: 'pass' },
      { key: 'policy', value: 'PASS', status: 'pass' },
    ],
    policyReasons: [
      { code: 'ZONE_PERMITTED', status: 'pass' },
      { code: 'SPEED_WITHIN_LIMIT', status: 'pass' },
      { code: 'PATH_CLEAR', status: 'pass' },
    ],
    aiRisk: 0.08,
    outcome: 'ALLOW',
    outcomeLabel: 'ALLOW',
    containment: [],
    latencyMs: 31,
    stages: [
      { label: 'Command received', detail: 'MOVE robot-01 → ZONE_B', status: 'info' },
      { label: 'Identity verified', detail: 'JWT valid • device signature matched', status: 'pass' },
      { label: 'Physical policy evaluated', detail: 'path clear • speed ratio 0.53', status: 'pass' },
      { label: 'AI behavior scored', detail: 'anomaly risk 0.08 • nominal', status: 'pass' },
      { label: 'Decision issued', detail: 'ALLOW • policy v1.4', status: 'pass' },
      { label: 'Containment confirmed', detail: 'not required', status: 'info' },
    ],
  },
  {
    id: 'stolen',
    name: 'Stolen Credential',
    blurb: 'A valid, unexpired credential replayed from an unbound controller.',
    command: 'MOVE → HUMAN_ZONE • 1.8 m/s',
    fields: [
      { key: 'identity', value: 'fleet-agent-01', status: 'warn' },
      { key: 'device', value: 'rogue-laptop', status: 'fail' },
      { key: 'robot', value: 'robot-01', status: 'info' },
      { key: 'destination', value: 'HUMAN_ZONE', status: 'fail' },
      { key: 'speed', value: '1.8 m/s', status: 'fail' },
      { key: 'policy', value: 'FAIL', status: 'fail' },
    ],
    policyReasons: [
      { code: 'DEVICE_MISMATCH', status: 'fail' },
      { code: 'ZONE_NOT_PERMITTED', status: 'fail' },
      { code: 'SPEED_EXCEEDED', status: 'fail' },
    ],
    aiRisk: 0.91,
    outcome: 'DENY',
    outcomeLabel: 'DENY + CONTAIN',
    note: 'The signature is genuine. The physical request is not survivable.',
    containment: ['Credential revoked', 'Identity quarantined', 'Robot E-STOP engaged'],
    latencyMs: 42,
    stages: [
      { label: 'Command received', detail: 'MOVE robot-01 → HUMAN_ZONE', status: 'info' },
      { label: 'Identity verified', detail: 'JWT valid • device binding FAILED', status: 'fail' },
      { label: 'Physical policy evaluated', detail: 'zone denied • speed 1.8 > 1.2 m/s', status: 'fail' },
      { label: 'AI behavior scored', detail: 'anomaly risk 0.91 • off-profile origin', status: 'fail' },
      { label: 'Decision issued', detail: 'DENY • 3 hard policy violations', status: 'fail' },
      { label: 'Containment confirmed', detail: 'revoked • quarantined • E-STOP', status: 'fail' },
    ],
  },
  {
    id: 'anomaly',
    name: 'AI-Detected Anomaly',
    blurb: 'Every field passes. The behavioral combination does not.',
    command: 'MOVE → ZONE_C • 1.45 m/s ×7',
    fields: [
      { key: 'credential', value: 'VALID', status: 'pass' },
      { key: 'device', value: 'VERIFIED', status: 'pass' },
      { key: 'destination', value: 'PERMITTED', status: 'pass' },
      { key: 'requested_speed', value: '1.45 m/s', status: 'warn' },
      { key: 'command_pattern', value: 'unusual burst + repetition', status: 'fail' },
      { key: 'static_policy', value: 'PASS', status: 'pass' },
    ],
    policyReasons: [
      { code: 'STATIC_POLICY_PASS', status: 'pass' },
      { code: 'BEHAVIOR_OFF_MANIFOLD', status: 'fail' },
      { code: 'BURST_REPETITION', status: 'fail' },
    ],
    aiRisk: 0.96,
    outcome: 'DENY',
    outcomeLabel: 'CRITICAL ANOMALY → DENY',
    note: 'Every individual field is allowed. The behavioral combination is not.',
    containment: ['Command denied', 'Identity flagged for review', 'Session rate-limited'],
    latencyMs: 38,
    stages: [
      { label: 'Command received', detail: '7th MOVE in 900 ms window', status: 'info' },
      { label: 'Identity verified', detail: 'JWT valid • device signature matched', status: 'pass' },
      { label: 'Physical policy evaluated', detail: 'all deterministic checks PASS', status: 'pass' },
      { label: 'AI behavior scored', detail: 'anomaly risk 0.96 • critical', status: 'fail' },
      { label: 'Decision issued', detail: 'DENY • behavioral risk evidence', status: 'fail' },
      { label: 'Containment confirmed', detail: 'session rate-limited • flagged', status: 'warn' },
    ],
  },
  {
    id: 'sensor',
    name: 'Physical Sensor Failure',
    blurb: 'Runtime force/torque telemetry classified mid-motion.',
    command: 'IN-FLIGHT TELEMETRY • robot-01',
    fields: [
      { key: 'telemetry_window', value: '15 samples • 315 ms', status: 'info' },
      { key: 'model_assessment', value: 'COLLISION / OBSTRUCTION SUSPECTED', status: 'fail' },
      { key: 'failure_probability', value: '0.94', status: 'fail' },
      { key: 'robot_state', value: 'MOVING → HALTING', status: 'warn' },
      { key: 'force_peak', value: '38.2 N • +410%', status: 'fail' },
      { key: 'nearby_humans', value: '2 detected', status: 'warn' },
    ],
    policyReasons: [
      { code: 'FORCE_THRESHOLD_EXCEEDED', status: 'fail' },
      { code: 'OBSTRUCTION_SUSPECTED', status: 'fail' },
      { code: 'HUMANS_IN_RADIUS', status: 'warn' },
    ],
    aiRisk: 0.94,
    outcome: 'ESTOP',
    outcomeLabel: 'E-STOP',
    note: 'Containment is not only about commands. Physical outcomes are governed too.',
    containment: ['Motion halted', 'Task suspended', 'Incident evidence sealed'],
    latencyMs: 27,
    stages: [
      { label: 'Command received', detail: 'telemetry stream • 15 samples', status: 'info' },
      { label: 'Identity verified', detail: 'robot-01 attested', status: 'pass' },
      { label: 'Physical policy evaluated', detail: 'force peak 38.2 N exceeds envelope', status: 'fail' },
      { label: 'AI behavior scored', detail: 'failure probability 0.94', status: 'fail' },
      { label: 'Decision issued', detail: 'E-STOP • immediate halt', status: 'fail' },
      { label: 'Containment confirmed', detail: 'motion halted in 27 ms', status: 'fail' },
    ],
  },
];

export const scenarioById = (id: ScenarioId): Scenario =>
  scenarios.find((s) => s.id === id) ?? scenarios[0];

/* --- Operations console mock state --------------------------------------- */

export const systemStatus = [
  { label: 'Broker', value: 'Online', tone: 'allow' as const },
  { label: 'AI Model', value: 'Ready', tone: 'allow' as const },
  { label: 'Simulator', value: 'Connected', tone: 'cyan' as const },
  { label: 'Audit Chain', value: 'Valid', tone: 'allow' as const },
];

export const consoleNav = [
  'Overview',
  'Live Decisions',
  'Incidents',
  'Identities',
  'Robots',
  'Policies',
  'Digital Twin',
] as const;

export type ConsoleNavItem = (typeof consoleNav)[number];

export interface IncidentRecord {
  id: string;
  time: string;
  identity: string;
  summary: string;
  outcome: Outcome;
}

export const incidents: IncidentRecord[] = [
  {
    id: 'INC-2291',
    time: '14:02:11.418',
    identity: 'fleet-agent-01',
    summary: 'Replayed credential from rogue-laptop → HUMAN_ZONE',
    outcome: 'DENY',
  },
  {
    id: 'INC-2288',
    time: '13:47:52.006',
    identity: 'fleet-agent-04',
    summary: 'Command burst ×7 in 900 ms — behavioral anomaly 0.96',
    outcome: 'DENY',
  },
  {
    id: 'INC-2284',
    time: '13:19:03.771',
    identity: 'robot-01',
    summary: 'Force/torque spike 38.2 N — obstruction suspected',
    outcome: 'ESTOP',
  },
  {
    id: 'INC-2280',
    time: '12:58:40.229',
    identity: 'fleet-agent-02',
    summary: 'Speed 1.35 m/s near dock — capped to 0.9 m/s',
    outcome: 'ALLOW_CONSTRAINED',
  },
  {
    id: 'INC-2277',
    time: '12:31:17.884',
    identity: 'fleet-agent-01',
    summary: 'Transport ZONE_A → ZONE_B, path clear',
    outcome: 'ALLOW',
  },
];

export const identities = [
  { id: 'fleet-agent-01', device: 'controller-01', grants: 4, state: 'QUARANTINED' },
  { id: 'fleet-agent-02', device: 'controller-01', grants: 3, state: 'ACTIVE' },
  { id: 'fleet-agent-04', device: 'controller-02', grants: 2, state: 'UNDER REVIEW' },
  { id: 'ops-supervisor', device: 'console-01', grants: 9, state: 'ACTIVE' },
];

export const robots = [
  { id: 'robot-01', model: 'AMR-240', zone: 'ZONE_A', speed: '0.00 m/s', state: 'E-STOP' },
  { id: 'robot-02', model: 'AMR-240', zone: 'ZONE_B', speed: '0.74 m/s', state: 'ACTIVE' },
  { id: 'robot-03', model: 'AMR-180', zone: 'DOCK', speed: '0.31 m/s', state: 'ACTIVE' },
  { id: 'robot-04', model: 'ARM-C7', zone: 'CELL_3', speed: '—', state: 'IDLE' },
];

export const policies = [
  { id: 'POL-ZONE-001', name: 'Human zone exclusion', mode: 'ENFORCE', hits: 41 },
  { id: 'POL-SPD-004', name: 'Speed envelope by zone', mode: 'ENFORCE', hits: 27 },
  { id: 'POL-DEV-002', name: 'Controller binding', mode: 'ENFORCE', hits: 12 },
  { id: 'POL-BEH-009', name: 'Command burst detection', mode: 'ENFORCE', hits: 8 },
  { id: 'POL-PTH-003', name: 'Corridor deviation', mode: 'OBSERVE', hits: 5 },
];
