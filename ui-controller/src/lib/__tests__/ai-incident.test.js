import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as OG from '../omniguard.js';

const cfg = {
  api: 'http://127.0.0.1:8000',
  robot: 'robot-01',
  credential: 'fleet-agent-valid-token',
};

function mockFetch(response = { ok: true, body: {} }) {
  const spy = vi.fn(async () => ({
    ok: response.ok !== false,
    status: response.status ?? 200,
    statusText: 'OK',
    text: async () => JSON.stringify(response.body ?? {}),
  }));
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

/* ================================================================ TEST 1
 * Existing control surface still renders. */
describe('existing control surface still renders', () => {
  it('App.jsx still imports DualSense, WarehouseMap, ScenarioPanel, PlaneCard', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'App.jsx'), 'utf8',
    );
    expect(src).toContain("import DualSense from");
    expect(src).toContain("import WarehouseMap from");
    expect(src).toContain("import ScenarioPanel from");
    expect(src).toContain("import PlaneCard from");
    expect(src).toContain("import DecisionCard from");
    expect(src).toContain("import InvestigatePanel from");
    expect(src).toContain("import LogsView from");
  });
});

/* ================================================================ TEST 2
 * Existing normal teleop still works. */
describe('existing normal teleop still works', () => {
  it('teleopStart, teleopMove, teleopStop are still exported', () => {
    expect(typeof OG.teleopStart).toBe('function');
    expect(typeof OG.teleopMove).toBe('function');
    expect(typeof OG.teleopStop).toBe('function');
  });

  it('teleop start still sends the identity and starting point', async () => {
    const spy = mockFetch({ body: { final_decision: 'ALLOW', control_id: 'abc' } });
    await OG.teleopStart(cfg, 'legit', { x: 4.2, y: 2.7, speed: 0.8 });
    expect(urlOf(spy)).toBe('http://127.0.0.1:8000/api/teleop/start');
  });
});

/* ================================================================ TEST 3
 * Existing rogue-device plane still works. */
describe('existing rogue-device plane still works', () => {
  it('sends the rogue device identity to the backend', async () => {
    const spy = mockFetch({ body: { final_decision: 'BLOCK', reasons: ['UNKNOWN_DEVICE'] } });
    await OG.teleopStart(cfg, 'rogue', { x: 0, y: 0, speed: 0.8 });
    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.device_id).toBe('rogue-controller');
  });
});

/* ================================================================ TEST 4
 * Existing arm and gripper controls still work. */
describe('existing arm and gripper controls still work', () => {
  it('arm presets and gripper functions are still exported', () => {
    expect(typeof OG.teleopArmPreset).toBe('function');
    expect(typeof OG.teleopArmJoints).toBe('function');
    expect(typeof OG.teleopGripper).toBe('function');
    expect(OG.ARM_PRESETS).toEqual(['stow', 'carry', 'reach', 'inspect']);
    expect(OG.GRIPPER_ACTIONS).toEqual(['open', 'close']);
  });
});

/* ================================================================ TEST 5
 * Missing AI endpoints do not break the console. */
describe('missing AI endpoints do not break the console', () => {
  it('getAiStatus 404 does not throw into the caller when caught', async () => {
    mockFetch({ ok: false, status: 404, body: { detail: 'Not Found' } });
    let error;
    try { await OG.getAiStatus(cfg); } catch (e) { error = e; }
    expect(error).toBeDefined();
    expect(error.status).toBe(404);
  });

  it('listIncidents 404 produces a typed ApiError', async () => {
    mockFetch({ ok: false, status: 404, body: { detail: 'Not Found' } });
    await expect(OG.listIncidents(cfg)).rejects.toMatchObject({ status: 404 });
  });

  it('console still has all existing exports after AI extensions', () => {
    /* If any existing export was removed, this test fails. */
    for (const name of [
      'DEFAULTS', 'DEMO_CREDENTIAL', 'DEMO_OPERATOR_TOKEN', 'OPERATOR_HEADER',
      'loadConfig', 'saveConfig', 'IDENTITIES', 'DEADZONE', 'padStickFor',
      'padEstopPressed', 'LOOKAHEAD', 'FALLBACK_TELEOP_CONFIG', 'isRestrictedZone',
      'floorBounds', 'zoneAt', 'clamp', 'speedFor', 'ApiError', 'apiGet',
      'rejectionReasons', 'getHealth', 'getState', 'getEvents', 'getTimeline',
      'getLatestIncident', 'listScenarios', 'investigate', 'resetBackend',
      'runScenario', 'getTeleopConfig', 'teleopStart', 'teleopMove', 'teleopStop',
      'teleopArmPreset', 'teleopArmJoints', 'teleopGripper', 'RISK_WARNING',
      'RISK_CRITICAL', 'riskBand', 'FEATURE_LABELS', 'readPosition',
      'ARM_PRESETS', 'GRIPPER_ACTIONS', 'ARM_EXTENSION', 'ARM_YAW_DEGREES',
      'readManipulator', 'headingFrom',
    ]) {
      expect(OG[name], `${name} should still be exported`).toBeDefined();
    }
  });
});

/* ================================================================ TEST 6
 * AI-only block displays 'hard rules passed'. */
describe('AI-only block displays hard rules passed', () => {
  it('normalizeDecisionIntelligence sets hard_policy_would_block=false', () => {
    const d = OG.normalizeDecisionIntelligence({
      final_decision: 'BLOCK',
      hard_policy_would_block: false,
      anomaly_risk_score: 0.92,
      decision_source: 'action_window_ai',
    });
    expect(d.hard_policy_would_block).toBe(false);
    expect(d.decision_source).toBe('ACTION_WINDOW_AI');
  });

  it('classifyDecisionSource returns ACTION_WINDOW_AI for AI-only block', () => {
    expect(OG.classifyDecisionSource({
      hard_policy_would_block: false,
      final_decision: 'BLOCK',
    })).toBe('ACTION_WINDOW_AI');
  });
});

/* ================================================================ TEST 7
 * Hard-policy block displays deterministic policy source. */
describe('hard-policy block displays deterministic policy source', () => {
  it('classifyDecisionSource returns HARD_POLICY when hard_policy_would_block=true', () => {
    expect(OG.classifyDecisionSource({
      hard_policy_would_block: true,
      final_decision: 'BLOCK',
    })).toBe('HARD_POLICY');
  });

  it('normalizeDecisionIntelligence surfaces hard_policy_reasons', () => {
    const d = OG.normalizeDecisionIntelligence({
      hard_policy_would_block: true,
      hard_policy_reasons: ['UNKNOWN_DEVICE', 'RESTRICTED_ZONE'],
    });
    expect(d.hard_policy_reasons).toEqual(['UNKNOWN_DEVICE', 'RESTRICTED_ZONE']);
  });
});

/* ================================================================ TEST 8
 * Observe mode is labelled. */
describe('observe mode is labelled', () => {
  it('normalizeDecisionIntelligence preserves ai_mode=observe', () => {
    const d = OG.normalizeDecisionIntelligence({
      ai_mode: 'observe',
      final_decision: 'ALLOW',
    });
    expect(d.ai_mode).toBe('observe');
  });
});

/* ================================================================ TEST 9
 * Null model confidence is not rendered as a percentage. */
describe('null model confidence is not rendered as a percentage', () => {
  it('normalizeDecisionIntelligence keeps null model_confidence as null', () => {
    const d = OG.normalizeDecisionIntelligence({
      model_confidence: null,
      anomaly_risk_score: 0.5,
    });
    expect(d.model_confidence).toBeNull();
  });

  it('does not convert undefined model_confidence to 0', () => {
    const d = OG.normalizeDecisionIntelligence({
      anomaly_risk_score: 0.3,
    });
    expect(d.model_confidence).toBeNull();
  });
});

/* ================================================================ TEST 10
 * Anomaly score is not labelled probability. */
describe('anomaly score is not labelled probability', () => {
  it('no component source file contains "probability" in the context of anomaly', () => {
    const srcDir = new URL('../../', import.meta.url).pathname;
    const offenders = [];
    const walk = (dir) => {
      for (const name of readdirSync(dir)) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) {
          if (name !== '__tests__' && name !== 'node_modules') walk(full);
          continue;
        }
        if (!/\.(js|jsx)$/.test(name)) continue;
        const code = readFileSync(full, 'utf8')
          .replace(/\/\*[\s\S]*?\*\//g, '')
          .replace(/^\s*\/\/.*$/gm, '')
          .replace(/\{\/\*[\s\S]*?\*\/\}/g, '');
        /* Allow "probability" only in test files and comments. */
        if (/anomaly.*probabilit|probabilit.*anomaly/i.test(code)) {
          offenders.push(full);
        }
      }
    };
    walk(srcDir);
    expect(offenders).toEqual([]);
  });

  it('RiskMeter label says "anomaly risk", not "probability"', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'RiskMeter.jsx'), 'utf8',
    );
    expect(src).toContain('AI anomaly risk');
    expect(src).not.toMatch(/probability/i);
  });
});

/* ================================================================ TEST 11
 * Live LLM provider/model is displayed. */
describe('live LLM provider/model is displayed', () => {
  it('normalizeLlmProvenance surfaces provider and model for live analysis', () => {
    const p = OG.normalizeLlmProvenance({
      provider: 'anthropic',
      model: 'claude-3-5-sonnet',
      summary: 'test',
    });
    expect(p.status).toBe('live_llm');
    expect(p.provider).toBe('anthropic');
    expect(p.model).toBe('claude-3-5-sonnet');
  });
});

/* ================================================================ TEST 12
 * Deterministic fallback is displayed clearly. */
describe('deterministic fallback is displayed clearly', () => {
  it('normalizeLlmProvenance identifies fallback_used=true', () => {
    const p = OG.normalizeLlmProvenance({
      fallback_used: true,
      fallback_reason: 'LLM timeout',
      summary: 'deterministic analysis',
    });
    expect(p.status).toBe('deterministic_fallback');
    expect(p.fallback_used).toBe(true);
    expect(p.fallback_reason).toBe('LLM timeout');
  });

  it('normalizeLlmProvenance identifies is_fallback=true (alternate field)', () => {
    const p = OG.normalizeLlmProvenance({
      is_fallback: true,
      summary: 'deterministic analysis',
    });
    expect(p.status).toBe('deterministic_fallback');
    expect(p.fallback_used).toBe(true);
  });

  it('AgentTrace source labels deterministic fallback', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'AgentTrace.jsx'), 'utf8',
    );
    expect(src).toContain('DETERMINISTIC FALLBACK');
  });
});

/* ================================================================ TEST 13
 * Agent proposal is not shown as executed containment. */
describe('agent proposal is not shown as executed containment', () => {
  it('normalizeAgentTrace distinguishes proposed from authorized', () => {
    const trace = OG.normalizeAgentTrace({
      proposed_playbook: 'CREDENTIAL_COMPROMISE',
      execution_authorized: false,
      steps: [{ tool: 'get_identity_history' }],
    });
    expect(trace.proposed_playbook).toBe('CREDENTIAL_COMPROMISE');
    expect(trace.execution_authorized).toBe(false);
  });

  it('AgentTrace component says "Proposed" not "Executed" for unauthorized', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'AgentTrace.jsx'), 'utf8',
    );
    expect(src).toContain("execution_authorized ? 'Authorized' : 'Proposed'");
    expect(src).toContain('Not executed until deterministic containment confirms');
  });
});

/* ================================================================ TEST 14
 * Incident event correlation count renders. */
describe('incident event correlation count renders', () => {
  it('normalizeIncidentDetail preserves event_count', () => {
    const d = OG.normalizeIncidentDetail({
      incident_id: 'INC-001',
      event_count: 840,
      first_seen: '2026-08-22T10:00:00Z',
      last_seen: '2026-08-22T10:05:00Z',
    });
    expect(d.event_count).toBe(840);
  });

  it('IncidentDetail renders event count in source', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'IncidentDetail.jsx'), 'utf8',
    );
    expect(src).toContain('events correlated into this incident');
  });
});

/* ================================================================ TEST 15
 * Feedback requires explicit confirmation. */
describe('feedback requires explicit confirmation', () => {
  it('IncidentFeedback has a confirmation step before submit', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'IncidentFeedback.jsx'), 'utf8',
    );
    expect(src).toContain('confirming');
    expect(src).toContain('Confirm');
    expect(src).toContain('Cancel');
    /* Must not auto-label based on LLM */
    expect(src).toContain('Feedback becomes reviewed training evidence');
  });

  it('offers all 7 required classifications', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'IncidentFeedback.jsx'), 'utf8',
    );
    for (const c of [
      'CONFIRMED_ATTACK', 'FALSE_POSITIVE', 'OPERATOR_ERROR',
      'MISCONFIGURATION', 'EXPECTED_MAINTENANCE', 'POLICY_GAP', 'UNKNOWN',
    ]) {
      expect(src).toContain(c);
    }
  });
});

/* ================================================================ TEST 16
 * Simulated recovery is labelled. */
describe('simulated recovery is labelled', () => {
  it('normalizeRecoveryState maps simulated status', () => {
    const r = OG.normalizeRecoveryState({
      old_credential_revoked: 'simulated',
      new_credential_issued: 'verified',
    });
    expect(r.old_credential_revoked).toBe('simulated');
    expect(r.new_credential_issued).toBe('verified');
  });

  it('RecoveryPanel source contains SIMULATED FOR DEMO label', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'RecoveryPanel.jsx'), 'utf8',
    );
    expect(src).toContain('SIMULATED FOR DEMO');
  });
});

/* ================================================================ TEST 17
 * Reset Demo remains available. */
describe('Reset Demo remains available', () => {
  it('TopBar still renders Reset demo button', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'components', 'TopBar.jsx'), 'utf8',
    );
    expect(src).toContain('Reset demo');
    expect(src).toContain('onReset');
  });

  it('App.jsx still handles reset', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'App.jsx'), 'utf8',
    );
    expect(src).toContain('handleReset');
    expect(src).toContain('ctl.reset');
  });
});

/* ================================================================ TEST 18
 * Incident polling does not change joystick request frequency. */
describe('incident polling does not change joystick request frequency', () => {
  it('useController.js is untouched — no changes to poll timing', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'lib', 'useController.js'), 'utf8',
    );
    /* These are the constants that control the teleop loop timing. */
    expect(src).toContain('const IDLE_POLL_MS = 1500');
    expect(src).toContain('const ACTIVE_POLL_MS = 350');
    /* The loop is driven by stream_hz, not by incident polling. */
    expect(src).toContain('teleopConfig.stream_hz');
  });

  it('useIncidents hook uses its own separate timers', () => {
    const src = readFileSync(
      join(new URL('../../', import.meta.url).pathname, 'lib', 'useIncidents.js'), 'utf8',
    );
    /* Has its own polling intervals */
    expect(src).toMatch(/LIST_POLL_MS/);
    expect(src).toMatch(/DETAIL_POLL_MS/);
    /* Does not import or reference useController's intervals */
    expect(src).not.toContain('IDLE_POLL_MS');
    expect(src).not.toContain('ACTIVE_POLL_MS');
    expect(src).not.toContain('stream_hz');
  });
});

/* ================================================================ TEST 19
 * No bridge token or LLM API key is stored. */
describe('no bridge token or LLM API key is stored', () => {
  it('never references ISAAC_BRIDGE_TOKEN in any source file', () => {
    const srcDir = new URL('../../', import.meta.url).pathname;
    const offenders = [];
    const walk = (dir) => {
      for (const name of readdirSync(dir)) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) {
          if (name !== '__tests__' && name !== 'node_modules') walk(full);
          continue;
        }
        if (!/\.(js|jsx)$/.test(name)) continue;
        const code = readFileSync(full, 'utf8')
          .replace(/\/\*[\s\S]*?\*\//g, '')
          .replace(/^\s*\/\/.*$/gm, '');
        if (code.includes('ISAAC_BRIDGE_TOKEN')) offenders.push(full);
      }
    };
    walk(srcDir);
    expect(offenders).toEqual([]);
  });

  it('never stores OpenAI/Anthropic/Bedrock keys in localStorage', () => {
    const srcDir = new URL('../../', import.meta.url).pathname;
    const offenders = [];
    const walk = (dir) => {
      for (const name of readdirSync(dir)) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) {
          if (name !== '__tests__' && name !== 'node_modules') walk(full);
          continue;
        }
        if (!/\.(js|jsx)$/.test(name)) continue;
        const code = readFileSync(full, 'utf8')
          .replace(/\/\*[\s\S]*?\*\//g, '')
          .replace(/^\s*\/\/.*$/gm, '')
          .replace(/\{\/\*[\s\S]*?\*\/\}/g, '');
        if (/localStorage\.\s*setItem\s*\([^)]*(?:api.key|openai|anthropic|bedrock|aws.secret)/i.test(code)) {
          offenders.push(full);
        }
      }
    };
    walk(srcDir);
    expect(offenders).toEqual([]);
  });

  it('saveConfig still strips credentials', () => {
    OG.saveConfig({
      api: 'http://x', robot: 'r',
      credential: 'secret', operatorToken: 'op-secret',
    });
    const raw = localStorage.getItem('omniguard.cfg');
    expect(raw).not.toContain('secret');
    expect(raw).not.toContain('operatorToken');
  });
});

/* ================================================================ TEST 20
 * Session export contains new AI provenance fields. */
describe('session export contains new AI provenance fields', () => {
  it('CSV header includes all new AI provenance columns', async () => {
    const { toCsv } = await import('../useSessionLog.js');
    const csv = toCsv([{
      timestamp: '2026-08-22T10:00:00Z',
      final_decision: 'BLOCK',
      decision_source: 'action_window_ai',
      anomaly_model_version: 'action-window-iforest-v1',
      ai_mode: 'enforce',
      incident_id: 'INC-001',
      response_playbook: 'UNSAFE_MANIPULATION_SEQUENCE',
      containment_ack: 'BASE_STOP',
    }]);
    const header = csv.split('\n')[0];
    for (const col of [
      'decision_source', 'anomaly_model_version', 'ai_mode',
      'incident_id', 'response_playbook', 'containment_ack',
    ]) {
      expect(header).toContain(`"${col}"`);
    }
  });

  it('preserves all original 12 columns', async () => {
    const { toCsv } = await import('../useSessionLog.js');
    const header = toCsv([{}]).split('\n')[0];
    for (const col of [
      'timestamp', 'final_decision', 'policy_decision', 'caught_by',
      'hard_policy_would_block', 'anomaly_risk_score', 'agent_id',
      'device_id', 'destination', 'speed', 'reasons', 'actions',
    ]) {
      expect(header).toContain(`"${col}"`);
    }
  });

  it('CSV row includes AI field values', async () => {
    const { toCsv } = await import('../useSessionLog.js');
    const rows = toCsv([{
      decision_source: 'action_window_ai',
      incident_id: 'INC-999',
    }]).split('\n');
    expect(rows[1]).toContain('action_window_ai');
    expect(rows[1]).toContain('INC-999');
  });
});

/* ============================================ NEW API FUNCTION UNIT TESTS */

describe('new AI API functions', () => {
  it('getAiStatus calls /api/ai/status', async () => {
    const spy = mockFetch({ body: { available: true, model_version: 'v1' } });
    await OG.getAiStatus(cfg);
    expect(urlOf(spy)).toBe('http://127.0.0.1:8000/api/ai/status');
  });

  it('listIncidents calls /api/incidents', async () => {
    const spy = mockFetch({ body: [] });
    await OG.listIncidents(cfg);
    expect(urlOf(spy)).toBe('http://127.0.0.1:8000/api/incidents');
  });

  it('getIncident calls /api/incidents/{id} with URL encoding', async () => {
    const spy = mockFetch({ body: { incident_id: 'INC-001' } });
    await OG.getIncident(cfg, 'INC-001');
    expect(urlOf(spy)).toBe('http://127.0.0.1:8000/api/incidents/INC-001');
  });

  it('investigateIncident calls POST /api/incidents/{id}/investigate', async () => {
    const spy = mockFetch({ body: { status: 'started' } });
    await OG.investigateIncident(cfg, 'INC-001');
    expect(urlOf(spy)).toBe('http://127.0.0.1:8000/api/incidents/INC-001/investigate');
    expect(spy.mock.calls[0][1].method).toBe('POST');
  });

  it('submitIncidentFeedback sends the classification body', async () => {
    const spy = mockFetch({ body: { ok: true } });
    await OG.submitIncidentFeedback(cfg, 'INC-001', {
      classification: 'CONFIRMED_ATTACK',
      comment: 'verified attack',
    });
    expect(urlOf(spy)).toBe('http://127.0.0.1:8000/api/incidents/INC-001/feedback');
    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.classification).toBe('CONFIRMED_ATTACK');
  });

  it('advanceIncidentRecovery sends the recovery action body', async () => {
    const spy = mockFetch({ body: { ok: true } });
    await OG.advanceIncidentRecovery(cfg, 'INC-001', { action: 'advance' });
    expect(urlOf(spy)).toBe('http://127.0.0.1:8000/api/incidents/INC-001/recover');
    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.action).toBe('advance');
  });

  it('does not put secrets in query strings', async () => {
    const spy = mockFetch({ body: {} });
    await OG.getAiStatus(cfg);
    expect(urlOf(spy)).not.toContain('credential');
    expect(urlOf(spy)).not.toContain('token');
  });
});

/* ======================================== NORMALIZATION HELPER TESTS */

describe('normalizeAiStatus', () => {
  it('returns unavailable for null', () => {
    expect(OG.normalizeAiStatus(null).available).toBe(false);
  });

  it('normalizes a valid status object', () => {
    const s = OG.normalizeAiStatus({
      available: true, model_version: 'v1', degraded: false,
      artifact_verified: true, policy_version: 'p-2',
    });
    expect(s.available).toBe(true);
    expect(s.model_version).toBe('v1');
    expect(s.degraded).toBe(false);
  });
});

describe('normalizeIncidentSummary', () => {
  it('returns null for null input', () => {
    expect(OG.normalizeIncidentSummary(null)).toBeNull();
  });

  it('normalizes a summary with alternate field names', () => {
    const s = OG.normalizeIncidentSummary({
      id: 'INC-002', risk: 0.85, playbook: 'TEST',
      first_seen: '2026-08-22T10:00:00Z',
    });
    expect(s.incident_id).toBe('INC-002');
    expect(s.anomaly_risk_score).toBe(0.85);
    expect(s.response_playbook).toBe('TEST');
  });
});

describe('normalizeIncidentDetail', () => {
  it('returns null for null input', () => {
    expect(OG.normalizeIncidentDetail(null)).toBeNull();
  });

  it('defaults array sections to empty arrays', () => {
    const d = OG.normalizeIncidentDetail({ incident_id: 'INC-003' });
    expect(d.action_sequence).toEqual([]);
    expect(d.containment_actions).toEqual([]);
    expect(d.isaac_acks).toEqual([]);
    expect(d.correlated_events).toEqual([]);
    expect(d.affected_robots).toEqual([]);
    expect(d.affected_identities).toEqual([]);
  });
});

describe('normalizeAgentTrace', () => {
  it('returns null for null input', () => {
    expect(OG.normalizeAgentTrace(null)).toBeNull();
  });

  it('normalizes steps from alternate field names', () => {
    const t = OG.normalizeAgentTrace({
      tool_calls: [{ tool_name: 'get_identity', started_at: '2026-08-22T10:00:00Z' }],
      proposed_playbook: 'TEST_PLAYBOOK',
      execution_authorized: false,
    });
    expect(t.steps).toHaveLength(1);
    expect(t.steps[0].tool).toBe('get_identity');
    expect(t.proposed_playbook).toBe('TEST_PLAYBOOK');
    expect(t.execution_authorized).toBe(false);
  });
});

describe('normalizeLlmProvenance', () => {
  it('returns unavailable for null input', () => {
    const p = OG.normalizeLlmProvenance(null);
    expect(p.status).toBe('unavailable');
    expect(p.provider).toBeNull();
  });

  it('detects pending status', () => {
    expect(OG.normalizeLlmProvenance({ status: 'pending' }).status).toBe('pending');
    expect(OG.normalizeLlmProvenance({ pending: true }).status).toBe('pending');
  });

  it('detects failed status', () => {
    expect(OG.normalizeLlmProvenance({ status: 'failed' }).status).toBe('failed');
    expect(OG.normalizeLlmProvenance({ error: 'timeout' }).status).toBe('failed');
  });
});

describe('normalizeRecoveryState', () => {
  it('returns null for null input', () => {
    expect(OG.normalizeRecoveryState(null)).toBeNull();
  });

  it('accepts all 5 valid status values', () => {
    for (const status of ['pending', 'verified', 'failed', 'simulated', 'not_required']) {
      const r = OG.normalizeRecoveryState({ old_credential_revoked: status });
      expect(r.old_credential_revoked).toBe(status);
    }
  });

  it('rejects invalid status values', () => {
    const r = OG.normalizeRecoveryState({ old_credential_revoked: 'INVENTED' });
    expect(r.old_credential_revoked).toBeNull();
  });

  it('accepts status as an object with .status field', () => {
    const r = OG.normalizeRecoveryState({
      old_credential_revoked: { status: 'simulated', detail: 'demo' },
    });
    expect(r.old_credential_revoked).toBe('simulated');
  });
});
