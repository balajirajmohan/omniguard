import { useState } from 'react';
import {
  AlertTriangle, Bot, Brain, ChevronDown, Clock, FileJson, GitBranch,
  Info, Layers, Loader2, MessageSquare, Play, RefreshCw, Shield, ShieldAlert, ShieldCheck,
  Terminal, Zap,
} from 'lucide-react';
import RiskMeter from './RiskMeter.jsx';
import AgentTrace from './AgentTrace.jsx';
import IncidentExplanation from './IncidentExplanation.jsx';
import RecoveryPanel from './RecoveryPanel.jsx';
import IncidentFeedback from './IncidentFeedback.jsx';
import { FEATURE_LABELS, investigateIncident, normalizeDecisionIntelligence, riskBand } from '../lib/omniguard.js';
import { exportJson } from '../lib/useSessionLog.js';

const when = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString([], { hour12: false }); } catch { return iso; }
};

function Section({ icon: Icon, iconCls, title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)}
      className="rounded-xl border border-line bg-sunken/30">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-3 py-2
                          text-[12px] font-semibold">
        <ChevronDown size={11}
          className={`shrink-0 transition-transform text-faint ${open ? '' : '-rotate-90'}`}
          aria-hidden="true" />
        <Icon size={12} className={`shrink-0 ${iconCls ?? 'text-faint'}`} aria-hidden="true" />
        {title}
      </summary>
      <div className="px-3 pb-3 pt-1">{children}</div>
    </details>
  );
}

function KV({ label, value, title }) {
  if (value == null) return null;
  return (
    <div className="flex items-baseline justify-between gap-2 rounded-md border border-line
                    bg-sunken/70 px-1.5 py-0.5">
      <dt className="truncate text-faint font-mono text-[9.5px]">{label}</dt>
      <dd className="shrink-0 tabular-nums text-dim font-mono text-[9.5px]"
        title={title}>{value}</dd>
    </div>
  );
}

/**
 * Full incident detail with all 13 sections.
 *
 * Renders each section as a collapsible card using backend-supplied data.
 * Never infers missing data. Timestamps are readable with raw ISO in tooltips.
 */
export default function IncidentDetail({ incident, cfg, onRefresh }) {
  const [investigating, setInvestigating] = useState(false);
  const [confirmInvestigate, setConfirmInvestigate] = useState(false);
  const [investigateError, setInvestigateError] = useState(null);
  const [llmLimitWarning, setLlmLimitWarning] = useState(false);

  if (!incident) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="text-[12px] text-faint">Select an incident from the list.</p>
      </div>
    );
  }

  const d = normalizeDecisionIntelligence(incident.raw);
  const risk = incident.anomaly_risk_score;
  const eventCount = incident.event_count;

  const handleInvestigate = async () => {
    setInvestigating(true);
    setInvestigateError(null);
    setLlmLimitWarning(false);
    setConfirmInvestigate(false);
    try {
      await investigateIncident(cfg, incident.incident_id);
      onRefresh?.();
    } catch (err) {
      if (err.status === 429 || err.message?.includes('LLM_CALL_LIMIT') || err.body?.detail === 'LLM_CALL_LIMIT') {
        setLlmLimitWarning(true);
      } else {
        setInvestigateError(err.message);
      }
    } finally {
      setInvestigating(false);
    }
  };

  const containmentObj = incident.containment;

  return (
    <div className="pane space-y-2">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-1.5 text-[14px]">
            <ShieldAlert size={14} className="text-bad" aria-hidden="true" />
            {incident.incident_id}
          </h3>
          <p className="mt-0.5 font-mono text-[10px] text-faint">
            {incident.status} · {when(incident.first_seen)}
            {incident.last_seen && ` → ${when(incident.last_seen)}`}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            className="btn btn-sm text-violet border-violet/45 hover:bg-violet/10"
            onClick={() => setConfirmInvestigate(true)}
            disabled={investigating}
            aria-label="Investigate incident with AI agent"
          >
            {investigating ? <Loader2 size={11} className="animate-spin" aria-hidden="true" /> : <Bot size={11} aria-hidden="true" />}
            {investigating ? 'Investigating…' : 'Investigate'}
          </button>
          <button className="btn btn-sm"
            onClick={() => exportJson(`incident-${incident.incident_id}`, incident.raw)}
            aria-label="Export incident as JSON">
            <FileJson size={11} aria-hidden="true" />
            Export
          </button>
        </div>
      </div>

      {/* Investigate Confirmation Modal / Notice */}
      {confirmInvestigate && (
        <div className="flex items-center gap-2 rounded-xl border border-violet/45 bg-violet/10 px-3 py-2">
          <Bot size={14} className="shrink-0 text-violet" aria-hidden="true" />
          <p className="flex-1 text-[11px] text-violet">
            Trigger AI agent investigation for {incident.incident_id}?
          </p>
          <div className="flex gap-1.5">
            <button onClick={() => setConfirmInvestigate(false)} className="btn btn-sm text-faint">Cancel</button>
            <button onClick={handleInvestigate} className="btn btn-sm btn-primary">Confirm</button>
          </div>
        </div>
      )}

      {/* LLM_CALL_LIMIT Warning */}
      {llmLimitWarning && (
        <div className="flex items-start gap-2.5 rounded-xl border border-warn/45 bg-warn/10 px-3 py-2" role="alert">
          <Info size={14} className="mt-0.5 shrink-0 text-warn" aria-hidden="true" />
          <p className="text-[11px] leading-relaxed text-warn">
            <b>LLM call limit reached for this session.</b> Deterministic fallback retained.
          </p>
        </div>
      )}

      {investigateError && (
        <p className="rounded-lg border border-bad/45 bg-bad/10 px-2 py-1 font-mono text-[10px] text-bad">
          Investigation error: {investigateError}
        </p>
      )}

      {/* Event correlation display (Phase 9) */}
      {eventCount != null && eventCount > 1 && (
        <div className="flex items-start gap-2 rounded-xl border border-info/45 bg-info/10
                        px-3 py-2" role="status" aria-label="Event correlation">
          <Layers size={13} className="mt-px shrink-0 text-info" aria-hidden="true" />
          <div>
            <p className="text-[11px] font-semibold text-info">
              {eventCount} events correlated into this incident
            </p>
            <div className="mt-1 flex flex-wrap gap-2 font-mono text-[9.5px] text-dim">
              {incident.first_seen && <span>First: {when(incident.first_seen)}</span>}
              {incident.last_seen && <span>Last: {when(incident.last_seen)}</span>}
              {incident.common_reason && (
                <span>Common reason: {incident.common_reason}</span>
              )}
            </div>
            {incident.affected_robots?.length > 0 && (
              <p className="mt-0.5 font-mono text-[9.5px] text-faint">
                Robots: {incident.affected_robots.join(', ')}
              </p>
            )}
            {incident.affected_identities?.length > 0 && (
              <p className="mt-0.5 font-mono text-[9.5px] text-faint">
                Identities: {incident.affected_identities.join(', ')}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Section 1: Executive summary */}
      {incident.executive_summary && (
        <Section icon={Shield} iconCls="text-info" title="Executive summary" defaultOpen>
          <p className="text-[11px] leading-relaxed text-dim">{incident.executive_summary}</p>
        </Section>
      )}

      {/* Section 2: Technical evidence */}
      {incident.technical_evidence && (
        <Section icon={Terminal} iconCls="text-violet" title="Technical evidence">
          <pre className="overflow-x-auto rounded-lg border border-line bg-sunken/70
                          px-2.5 py-1.5 font-mono text-[9.5px] text-dim whitespace-pre-wrap">
            {typeof incident.technical_evidence === 'string'
              ? incident.technical_evidence
              : JSON.stringify(incident.technical_evidence, null, 2)}
          </pre>
        </Section>
      )}

      {/* Section 3: Identity and device */}
      {incident.identity && (
        <Section icon={ShieldCheck} iconCls="text-ok" title="Identity and device">
          <dl className="grid grid-cols-2 gap-1">
            {Object.entries(incident.identity).map(([k, v]) => (
              <KV key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
            ))}
          </dl>
        </Section>
      )}

      {/* Section 4: Action sequence */}
      {incident.action_sequence.length > 0 && (
        <Section icon={Zap} title="Base / arm / gripper action sequence">
          <ol className="space-y-0.5">
            {incident.action_sequence.map((a, i) => (
              <li key={i} className="flex items-center gap-1 font-mono text-[9.5px] text-dim">
                <span className="w-4 shrink-0 text-right text-faint">{i + 1}</span>
                <span>{typeof a === 'string' ? a : JSON.stringify(a)}</span>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* Section 5: Robot and zone context */}
      {incident.robot_context && (
        <Section icon={GitBranch} title="Robot and zone context">
          <dl className="grid grid-cols-2 gap-1">
            {Object.entries(incident.robot_context).map(([k, v]) => (
              <KV key={k} label={k.replace(/_/g, ' ')}
                value={typeof v === 'object' ? JSON.stringify(v) : String(v)} />
            ))}
          </dl>
        </Section>
      )}

      {/* Section 6: AI model evidence — Shows all 3 risk metrics separately */}
      {(d || incident.ai_evidence) && (
        <Section icon={Brain} iconCls="text-info" title="AI model evidence" defaultOpen={!!risk}>
          <div className="space-y-2">
            {/* Three distinct risk scores */}
            <div className="grid grid-cols-3 gap-1.5 font-mono text-[9.5px]">
              <div className="rounded-lg border border-line bg-sunken/70 px-2 py-1 text-center">
                <span className="block text-faint text-[8.5px]">Anomaly Risk (iForest)</span>
                <span className="font-bold text-dim">{d?.anomaly_risk_score != null ? d.anomaly_risk_score.toFixed(2) : '—'}</span>
              </div>
              <div className="rounded-lg border border-line bg-sunken/70 px-2 py-1 text-center">
                <span className="block text-faint text-[8.5px]">Behavioral Rule Score</span>
                <span className="font-bold text-dim">{d?.behavioral_rule_score != null ? d.behavioral_rule_score.toFixed(2) : '—'}</span>
              </div>
              <div className="rounded-lg border border-line bg-sunken/70 px-2 py-1 text-center">
                <span className="block text-faint text-[8.5px]">Effective Risk</span>
                <span className="font-bold text-info">{d?.effective_risk != null ? d.effective_risk.toFixed(2) : '—'}</span>
              </div>
            </div>

            {risk != null && (
              <RiskMeter risk={risk} modelVersion={d?.anomaly_model_version} unavailable={d?.model_degraded} />
            )}

            {d?.anomaly_features && (
              <dl className="mt-2 grid grid-cols-2 gap-1 font-mono text-[9.5px]">
                {Object.entries(d.anomaly_features).map(([k, val]) => (
                  <KV key={k} label={FEATURE_LABELS[k] ?? k} value={Number(val)} />
                ))}
              </dl>
            )}

            {d?.model_confidence != null && (
              <p className="mt-1 font-mono text-[10px] text-faint">
                Model confidence: {(d.model_confidence * 100).toFixed(1)}%
              </p>
            )}
          </div>
        </Section>
      )}

      {/* Section 7: Hard-policy evidence */}
      {(incident.hard_policy || incident.hard_policy_evidence) && (
        <Section icon={ShieldAlert} iconCls="text-bad" title="Hard-policy evidence">
          <pre className="overflow-x-auto rounded-lg border border-line bg-sunken/70
                          px-2.5 py-1.5 font-mono text-[9.5px] text-dim whitespace-pre-wrap">
            {typeof (incident.hard_policy ?? incident.hard_policy_evidence) === 'string'
              ? (incident.hard_policy ?? incident.hard_policy_evidence)
              : JSON.stringify(incident.hard_policy ?? incident.hard_policy_evidence, null, 2)}
          </pre>
        </Section>
      )}

      {/* Section 8: Containment actions */}
      {containmentObj && (
        <Section icon={AlertTriangle} iconCls="text-warn" title="Containment actions" defaultOpen>
          <div className="space-y-1.5 font-mono text-[10px]">
            {containmentObj.status && (
              <div className="flex items-center justify-between rounded-md border border-line bg-sunken/70 px-2 py-1">
                <span className="text-faint">Containment Status:</span>
                <span className="font-bold text-warn">{containmentObj.status}</span>
              </div>
            )}
            {containmentObj.attempted && (
              <div>
                <span className="label mb-0.5">Attempted</span>
                <p className="text-dim">{Array.isArray(containmentObj.attempted) ? containmentObj.attempted.join(', ') : String(containmentObj.attempted)}</p>
              </div>
            )}
            {containmentObj.acknowledged && (
              <div>
                <span className="label mb-0.5">Acknowledged</span>
                <p className="text-ok">{Array.isArray(containmentObj.acknowledged) ? containmentObj.acknowledged.join(', ') : String(containmentObj.acknowledged)}</p>
              </div>
            )}
            {containmentObj.failed && (
              <div>
                <span className="label mb-0.5 text-bad">Failed</span>
                <p className="text-bad">{Array.isArray(containmentObj.failed) ? containmentObj.failed.join(', ') : String(containmentObj.failed)}</p>
              </div>
            )}
            {containmentObj.unverified && (
              <div>
                <span className="label mb-0.5 text-warn">Unverified</span>
                <p className="text-warn">{Array.isArray(containmentObj.unverified) ? containmentObj.unverified.join(', ') : String(containmentObj.unverified)}</p>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Section 9: Isaac / Bridge acknowledgements */}
      {incident.isaac_acks.length > 0 && (
        <Section icon={Clock} title="Isaac bridge acknowledgements">
          <ol className="space-y-0.5">
            {incident.isaac_acks.map((a, i) => (
              <li key={i} className="font-mono text-[10px] text-dim">
                {typeof a === 'string' ? a : JSON.stringify(a)}
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* Section 10: Agent investigation */}
      {incident.agent_trace && (
        <Section icon={Bot} iconCls="text-violet" title="Agent investigation" defaultOpen>
          <AgentTrace raw={incident.agent_trace} />
        </Section>
      )}

      {/* Section 11: LLM explanation and provenance */}
      {incident.llm_explanation && (
        <Section icon={Brain} iconCls="text-info" title="LLM explanation and provenance" defaultOpen>
          <IncidentExplanation raw={incident.llm_explanation} />
        </Section>
      )}

      {/* Section 12: Feedback */}
      <Section icon={MessageSquare} title="Feedback">
        <IncidentFeedback incidentId={incident.incident_id}
          existingFeedback={incident.human_feedback} cfg={cfg} />
      </Section>

      {/* Section 13: Recovery */}
      <Section icon={RefreshCw} title="Recovery" defaultOpen>
        <RecoveryPanel incidentId={incident.incident_id}
          raw={incident.recovery} cfg={cfg} onRefresh={onRefresh} />
      </Section>

      {/* Raw events (expandable for Phase 9 event correlation) */}
      {incident.correlated_events.length > 0 && (
        <Section icon={Layers} title={`Raw events (${incident.correlated_events.length})`}>
          <div className="max-h-48 overflow-y-auto">
            <pre className="rounded-lg border border-line bg-sunken/70 px-2 py-1
                            font-mono text-[9px] text-faint whitespace-pre-wrap">
              {JSON.stringify(incident.correlated_events, null, 2)}
            </pre>
          </div>
        </Section>
      )}
    </div>
  );
}

