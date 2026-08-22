import { useState } from 'react';
import {
  AlertTriangle, Bot, Brain, ChevronDown, Clock, FileJson, GitBranch,
  Layers, MessageSquare, RefreshCw, Shield, ShieldAlert, ShieldCheck,
  Terminal, Zap,
} from 'lucide-react';
import RiskMeter from './RiskMeter.jsx';
import AgentTrace from './AgentTrace.jsx';
import IncidentExplanation from './IncidentExplanation.jsx';
import RecoveryPanel from './RecoveryPanel.jsx';
import IncidentFeedback from './IncidentFeedback.jsx';
import { FEATURE_LABELS, normalizeDecisionIntelligence, riskBand } from '../lib/omniguard.js';
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
export default function IncidentDetail({ incident, cfg }) {
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
        <button className="btn btn-sm"
          onClick={() => exportJson(`incident-${incident.incident_id}`, incident.raw)}
          aria-label="Export incident as JSON">
          <FileJson size={11} aria-hidden="true" />
          Export
        </button>
      </div>

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
            {incident.affected_robots.length > 0 && (
              <p className="mt-0.5 font-mono text-[9.5px] text-faint">
                Robots: {incident.affected_robots.join(', ')}
              </p>
            )}
            {incident.affected_identities.length > 0 && (
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

      {/* Section 6: AI model evidence */}
      {(d || incident.ai_model_evidence) && (
        <Section icon={Brain} iconCls="text-info" title="AI model evidence" defaultOpen={!!risk}>
          {risk != null && (
            <RiskMeter risk={risk} modelVersion={d?.anomaly_model_version}
              unavailable={d?.model_degraded} />
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
          {incident.ai_model_evidence && typeof incident.ai_model_evidence === 'object' &&
            !d?.anomaly_features && (
            <pre className="mt-1 overflow-x-auto rounded-lg border border-line bg-sunken/70
                            px-2 py-1 font-mono text-[9.5px] text-dim whitespace-pre-wrap">
              {JSON.stringify(incident.ai_model_evidence, null, 2)}
            </pre>
          )}
        </Section>
      )}

      {/* Section 7: Hard-policy evidence */}
      {incident.hard_policy_evidence && (
        <Section icon={ShieldAlert} iconCls="text-bad" title="Hard-policy evidence">
          <pre className="overflow-x-auto rounded-lg border border-line bg-sunken/70
                          px-2.5 py-1.5 font-mono text-[9.5px] text-dim whitespace-pre-wrap">
            {typeof incident.hard_policy_evidence === 'string'
              ? incident.hard_policy_evidence
              : JSON.stringify(incident.hard_policy_evidence, null, 2)}
          </pre>
        </Section>
      )}

      {/* Section 8: Containment actions */}
      {incident.containment_actions.length > 0 && (
        <Section icon={AlertTriangle} iconCls="text-warn" title="Containment actions">
          <ol className="space-y-0.5">
            {incident.containment_actions.map((a, i) => (
              <li key={i} className="font-mono text-[10px] text-dim">
                {typeof a === 'string' ? a : JSON.stringify(a)}
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* Section 9: Isaac acknowledgements */}
      {incident.isaac_acks.length > 0 && (
        <Section icon={Clock} title="Isaac acknowledgements">
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
        <Section icon={Bot} iconCls="text-violet" title="Agent investigation">
          <AgentTrace raw={incident.agent_trace} />
        </Section>
      )}

      {/* Section 11: LLM explanation and provenance */}
      {incident.explanation && (
        <Section icon={Brain} iconCls="text-info" title="LLM explanation and provenance">
          <IncidentExplanation raw={incident.explanation} />
        </Section>
      )}

      {/* Section 12: Feedback */}
      <Section icon={MessageSquare} title="Feedback">
        <IncidentFeedback incidentId={incident.incident_id}
          existingFeedback={incident.feedback} cfg={cfg} />
      </Section>

      {/* Section 13: Recovery */}
      <Section icon={RefreshCw} title="Recovery">
        <RecoveryPanel incidentId={incident.incident_id}
          raw={incident.recovery} cfg={cfg} />
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
