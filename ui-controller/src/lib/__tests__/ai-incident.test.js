import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as OG from '../omniguard.js';

const cfg = {
  api: 'http://127.0.0.1:8000',
  robot: 'robot-01',
  credential: 'fleet-agent-valid-token',
  operatorToken: 'omniguard-operator',
};

function mockFetch(response = { ok: true, body: {} }) {
  const spy = vi.fn(async (_url, opts = {}) => {
    if (response.requireOperatorHeader) {
      const headers = opts.headers || {};
      const opHeader = headers['X-OmniGuard-Operator'] || headers['x-omniguard-operator'];
      if (!opHeader) {
        return {
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          text: async () => JSON.stringify({ detail: 'Operator authentication required' }),
        };
      }
    }
    if (response.validateBody) {
      const body = opts.body ? JSON.parse(opts.body) : {};
      const invalid = response.validateBody(body);
      if (invalid) {
        return {
          ok: false,
          status: 422,
          statusText: 'Unprocessable Entity',
          text: async () => JSON.stringify({ detail: invalid }),
        };
      }
    }
    return {
      ok: response.ok !== false,
      status: response.status ?? 200,
      statusText: 'OK',
      text: async () => JSON.stringify(response.body ?? {}),
    };
  });
  globalThis.fetch = spy;
  return spy;
}

const urlOf = (spy, call = 0) => spy.mock.calls[call][0];

beforeEach(() => {
  globalThis.localStorage = {
    store: {},
    getItem(k) { return this.store[k] ?? null; },
    setItem(k, v) { this.store[k] = v; },
    removeItem(k) { delete this.store[k]; },
  };
  globalThis.sessionStorage = {
    store: {},
    getItem(k) { return this.store[k] ?? null; },
    setItem(k, v) { this.store[k] = v; },
    removeItem(k) { delete this.store[k]; },
  };
});

/* ================================================================ MANDATORY FIX 1
 * Send X-OmniGuard-Operator on investigate, feedback and recover requests. */
describe('X-OmniGuard-Operator authorization on incident mutations', () => {
  it('investigateIncident sends X-OmniGuard-Operator header', async () => {
    const spy = mockFetch({ requireOperatorHeader: true, body: { status: 'started' } });
    const res = await OG.investigateIncident(cfg, 'INC-100');
    expect(res.status).toBe('started');
    const headers = spy.mock.calls[0][1].headers;
    expect(headers['X-OmniGuard-Operator']).toBe('omniguard-operator');
  });

  it('submitIncidentFeedback sends X-OmniGuard-Operator header', async () => {
    const spy = mockFetch({ requireOperatorHeader: true, body: { status: 'recorded' } });
    const res = await OG.submitIncidentFeedback(cfg, 'INC-100', { classification: 'FALSE_POSITIVE', notes: 'test' });
    expect(res.status).toBe('recorded');
    const headers = spy.mock.calls[0][1].headers;
    expect(headers['X-OmniGuard-Operator']).toBe('omniguard-operator');
  });

  it('advanceIncidentRecovery sends X-OmniGuard-Operator header', async () => {
    const spy = mockFetch({ requireOperatorHeader: true, body: { state: 'CREDENTIAL_ROTATION_REQUIRED' } });
    const res = await OG.advanceIncidentRecovery(cfg, 'INC-100', {});
    expect(res.state).toBe('CREDENTIAL_ROTATION_REQUIRED');
    const headers = spy.mock.calls[0][1].headers;
    expect(headers['X-OmniGuard-Operator']).toBe('omniguard-operator');
  });
});

/* ================================================================ RECOVERY STAGE EVIDENCE PROGRESSION FIX
 * Stage-appropriate evidence selection test. */
describe('Recovery stage-appropriate evidence progression', () => {
  it('submits evidence corresponding to recovery state', async () => {
    const spy = mockFetch({ body: { state: 'DEVICE_ATTESTATION_REQUIRED' } });

    // Step 1: CREDENTIAL_ROTATION_REQUIRED
    await OG.advanceIncidentRecovery(cfg, 'INC-100', {
      evidence: { old_credential_revoked: true, new_credential_issued: true },
    });
    const body1 = JSON.parse(spy.mock.calls[0][1].body);
    expect(body1.evidence).toEqual({ old_credential_revoked: true, new_credential_issued: true });

    // Step 2: DEVICE_ATTESTATION_REQUIRED
    await OG.advanceIncidentRecovery(cfg, 'INC-100', {
      evidence: { device_attested: true },
    });
    const body2 = JSON.parse(spy.mock.calls[1][1].body);
    expect(body2.evidence).toEqual({ device_attested: true });
  });
});

/* ================================================================ HTTP 200 LLM_CALL_LIMIT FIX
 * Inspection of HTTP 200 { ok: false, error: "LLM_CALL_LIMIT" } responses. */
describe('HTTP 200 LLM_CALL_LIMIT response handling', () => {
  it('returns JSON payload with ok: false and error: LLM_CALL_LIMIT on HTTP 200', async () => {
    mockFetch({
      ok: true,
      status: 200,
      body: { ok: false, error: 'LLM_CALL_LIMIT', call_count: 2, max_calls_per_incident: 2 },
    });
    const res = await OG.investigateIncident(cfg, 'INC-100');
    expect(res.ok).toBe(false);
    expect(res.error).toBe('LLM_CALL_LIMIT');
  });
});

/* ================================================================ MANDATORY FIX 2 & 3
 * Payload compatibility (notes field for feedback, {} or {evidence} for recovery). */
describe('Feedback and recovery payload shape compatibility', () => {
  it('feedback accepts notes field and rejects comment field (422 test)', async () => {
    mockFetch({
      validateBody: (b) => {
        if ('comment' in b) return 'Field "comment" not allowed, use "notes"';
        if (!('classification' in b)) return 'Field "classification" required';
        return null;
      },
      body: { status: 'ok' },
    });

    // Valid payload with notes
    await expect(OG.submitIncidentFeedback(cfg, 'INC-100', { classification: 'FALSE_POSITIVE', notes: 'Valid note' })).resolves.toEqual({ status: 'ok' });

    // Invalid payload with comment triggers 422
    mockFetch({
      validateBody: (b) => ('comment' in b ? 'Unprocessable' : null),
    });
    await expect(OG.submitIncidentFeedback(cfg, 'INC-100', { classification: 'FALSE_POSITIVE', comment: 'Bad' })).rejects.toThrow('Unprocessable');
  });

  it('recovery start sends {} and advancement sends evidence object', async () => {
    mockFetch({
      validateBody: (b) => {
        if ('action' in b) return 'Field "action" not recognized; expected {} or {evidence} or {force_state}';
        return null;
      },
      body: { state: 'DEVICE_ATTESTATION_REQUIRED' },
    });

    // Empty payload starts recovery
    await expect(OG.advanceIncidentRecovery(cfg, 'INC-100', {})).resolves.toEqual({ state: 'DEVICE_ATTESTATION_REQUIRED' });

    // Evidence payload advances recovery
    await expect(OG.advanceIncidentRecovery(cfg, 'INC-100', { evidence: { old_credential_revoked: true, new_credential_issued: true } })).resolves.toEqual({ state: 'DEVICE_ATTESTATION_REQUIRED' });
  });
});

/* ================================================================ BACKEND MAIN COMMIT 65737e3 FIXTURES
 * Exact backend main commit fixtures. */
describe('Normalization of backend main commit 65737e3 response fixtures', () => {
  const backendFixture = {
    id: 'INC-2026-0822-001',
    status: 'CREDENTIAL_ROTATION_REQUIRED',
    first_event_at: '2026-08-22T10:15:30.000Z',
    last_event_at: '2026-08-22T10:16:00.000Z',
    agent_id: 'fleet-agent-01',
    device_id: 'rogue-controller-01',
    robot_id: 'robot-01',
    demo_run_id: 'run-8821',
    playbook: 'CONTAIN_UNAUTHORIZED_MOVEMENT',
    model_version: 'iforest-v2.1',
    policy_version: 'policy-2026.08',
    decision_source: 'hybrid_rule_ml',
    ai_evidence: {
      decision_source: 'hybrid_rule_ml',
      anomaly_risk_score: 0.88,
      behavioral_rule_score: 0.95,
      effective_risk: 0.92,
      anomaly_features: { speed: 3.5, restricted_zone_entry: 1 },
      ai_mode: 'enforce',
      model_version: 'iforest-v2.1',
      model_confidence: 0.91,
      artifact_verified: true,
      model_degraded: false,
      hold_stop: {
        stop_requested: true,
        stop_request_accepted: true,
        stop_confirmed: true,
        stop_stage: 'CONFIRMED',
        stop_ack: 'ISAAC_ACK_ESTOP',
      },
    },
    hard_policy: {
      would_block: true,
      reasons: ['RESTRICTED_ZONE_VIOLATION'],
    },
    containment: {
      status: 'CONTAINED',
      attempted: ['BASE_DISABLE', 'BRAKE_ENGAGE'],
      acknowledged: ['BASE_DISABLE'],
      failed: [],
      unverified: ['BRAKE_ENGAGE'],
      bridge_acknowledgements: ['ISAAC_ACK_BASE_DISABLE_OK'],
    },
    llm_explanation: {
      summary: 'High-speed navigation inside human-restricted zone.',
      provider: 'anthropic',
      model: 'claude-3-5-sonnet',
      fallback_used: false,
      technical_summary: 'Robot velocity 3.5 m/s exceeded safe threshold in restricted area.',
      physical_impact: 'Potential collision risk with human operators.',
      root_cause: 'Compromised rogue device sending unauthorized movement commands.',
      why_suspicious: ['Speed exceeds max threshold', 'Zone entry unauthorized'],
      containment_taken: ['Base stopped immediately', 'Lease revoked'],
    },
    human_feedback: {
      classification: 'CONFIRMED_ATTACK',
      notes: 'Verified malicious device attempted unauthorized navigation.',
      reviewed_by: 'operator-1',
      reviewed_at: '2026-08-22T10:20:00.000Z',
    },
    agent_trace: {
      agent_mode: 'autonomous_investigation',
      provider: 'anthropic',
      model: 'claude-3-5-sonnet',
      fallback_used: false,
      proposed_playbook: 'CONTAIN_UNAUTHORIZED_MOVEMENT',
      execution_authorized: true,
      tool_trace: [
        { tool: 'query_identity_history', at: '2026-08-22T10:15:31.000Z', result: 'Found rogue device', ok: true },
        { tool: 'check_zone_policy', at: '2026-08-22T10:15:32.000Z', result: 'Restricted zone active', ok: true },
      ],
    },
    recovery: {
      state: 'CREDENTIAL_ROTATION_REQUIRED',
      label: 'IdP Credential Rotation Required',
      simulated: true,
      evidence: { old_credential_revoked: false, new_credential_issued: false },
      history: [{ state: 'CREDENTIAL_ROTATION_REQUIRED' }],
      idp_workflow_complete: false,
      runtime_access_restored: false,
      can_advance: true,
    },
  };

  it('normalizes incident summary from backend 65737e3 fields', () => {
    const sum = OG.normalizeIncidentSummary(backendFixture);
    expect(sum.incident_id).toBe('INC-2026-0822-001');
    expect(sum.first_seen).toBe('2026-08-22T10:15:30.000Z');
    expect(sum.last_seen).toBe('2026-08-22T10:16:00.000Z');
    expect(sum.demo_run_id).toBe('run-8821');
    expect(sum.decision_source).toBe('hybrid_rule_ml');
    expect(sum.anomaly_risk_score).toBe(0.88);
    expect(sum.behavioral_rule_score).toBe(0.95);
    expect(sum.effective_risk).toBe(0.92);
  });

  it('normalizes hard_policy object (would_block & reasons)', () => {
    const d = OG.normalizeDecisionIntelligence(backendFixture);
    expect(d.hard_policy_would_block).toBe(true);
    expect(d.hard_policy_reasons).toEqual(['RESTRICTED_ZONE_VIOLATION']);
  });

  it('normalizes physical stop fields from ai_evidence.hold_stop', () => {
    const d = OG.normalizeDecisionIntelligence(backendFixture);
    expect(d.stop_requested).toBe(true);
    expect(d.stop_confirmed).toBe(true);
    expect(d.robot_stopped).toBe(true);
    expect(d.stop_ack).toBe('ISAAC_ACK_ESTOP');
  });

  it('normalizes agent step timestamp from field "at"', () => {
    const trace = OG.normalizeAgentTrace(backendFixture.agent_trace);
    expect(trace.steps[0].timestamp).toBe('2026-08-22T10:15:31.000Z');
  });

  it('normalizes why_suspicious and containment_taken arrays in LLM provenance', () => {
    const prov = OG.normalizeLlmProvenance(backendFixture.llm_explanation);
    expect(prov.why_suspicious).toBe('Speed exceeds max threshold, Zone entry unauthorized');
    expect(prov.containment_taken).toBe('Base stopped immediately, Lease revoked');
  });

  it('normalizes nested /api/ai/status response', () => {
    const s = OG.normalizeAiStatus({
      command_anomaly: { available: true, model_version: 'v2.1', degraded: false },
    });
    expect(s.available).toBe(true);
    expect(s.model_version).toBe('v2.1');
    expect(s.degraded).toBe(false);
  });
});

/* ================================================================ MANDATORY FIX 7 & 8
 * Decision source exact values & no heuristic replacement. */
describe('Exact decision source values & no heuristic replacement', () => {
  it('supports all 7 exact decision sources without modifying backend decision_source', () => {
    const sources = [
      'hard_policy',
      'action_window_ai',
      'behavioral_rule',
      'hybrid_rule_ml',
      'ai_warning',
      'deterministic_fallback',
      'none',
    ];
    for (const src of sources) {
      expect(OG.classifyDecisionSource({ decision_source: src })).toBe(src);
    }
  });

  it('never heuristically replaces a backend-provided decision_source', () => {
    expect(OG.classifyDecisionSource({ decision_source: 'behavioral_rule', hard_policy_would_block: false, final_decision: 'BLOCK' })).toBe('behavioral_rule');
    expect(OG.classifyDecisionSource({ decision_source: 'hybrid_rule_ml', hard_policy_would_block: true })).toBe('hybrid_rule_ml');
  });
});

/* ================================================================ MANDATORY FIX 13 & 14
 * Physical stop truth fields & Session log CSV exports. */
describe('Physical stop truth fields and CSV exports', () => {
  it('normalizeDecisionIntelligence preserves stop fields and enforces robot_stopped truth', () => {
    // When stop_confirmed is false, robot_stopped is false
    const d1 = OG.normalizeDecisionIntelligence({
      stop_requested: true,
      stop_request_accepted: true,
      stop_confirmed: false,
      stop_stage: 'PENDING_ACK',
    });
    expect(d1.stop_requested).toBe(true);
    expect(d1.stop_confirmed).toBe(false);
    expect(d1.robot_stopped).toBe(false);

    // ONLY when stop_confirmed is true is robot_stopped true
    const d2 = OG.normalizeDecisionIntelligence({
      stop_requested: true,
      stop_request_accepted: true,
      stop_confirmed: true,
      stop_stage: 'CONFIRMED',
      stop_ack: 'ISAAC_ACK_ESTOP',
    });
    expect(d2.stop_confirmed).toBe(true);
    expect(d2.robot_stopped).toBe(true);
    expect(d2.stop_ack).toBe('ISAAC_ACK_ESTOP');
  });

  it('CSV export includes demo_run_id, behavioral_rule_score, effective_risk, and stop fields', async () => {
    const { toCsv } = await import('../useSessionLog.js');
    const csv = toCsv([
      {
        timestamp: '2026-08-22T10:00:00Z',
        final_decision: 'BLOCK',
        decision_source: 'hybrid_rule_ml',
        demo_run_id: 'run-990',
        behavioral_rule_score: 0.95,
        effective_risk: 0.92,
        stop_requested: true,
        stop_request_accepted: true,
        stop_confirmed: true,
        stop_stage: 'CONFIRMED',
        stop_ack: 'ACK_ESTOP',
      },
    ]);
    const header = csv.split('\n')[0];
    const row = csv.split('\n')[1];

    for (const col of [
      'demo_run_id',
      'behavioral_rule_score',
      'effective_risk',
      'stop_requested',
      'stop_request_accepted',
      'stop_confirmed',
      'robot_stopped',
      'stop_stage',
      'stop_ack',
    ]) {
      expect(header).toContain(`"${col}"`);
    }
    expect(row).toContain('run-990');
    expect(row).toContain('0.95');
    expect(row).toContain('0.92');
    expect(row).toContain('ACK_ESTOP');
  });
});
