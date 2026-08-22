import { AlertTriangle, Brain, ChevronDown, Eye, Shield, ShieldX } from 'lucide-react';
import { useState } from 'react';
import RiskMeter from './RiskMeter.jsx';
import {
  classifyDecisionSource, FEATURE_LABELS, normalizeDecisionIntelligence,
} from '../lib/omniguard.js';

/* Decision-source badge labels. Sorted strongest to weakest for presentation. */
const SOURCE_BADGE = {
  HARD_POLICY:      { label: 'Hard policy',       cls: 'border-bad/55 bg-bad/10 text-bad' },
  ACTION_WINDOW_AI: { label: 'Action-window AI',  cls: 'border-info/55 bg-info/10 text-info' },
  AI_WARNING:       { label: 'AI warning',         cls: 'border-warn/55 bg-warn/10 text-warn' },
  FALLBACK:         { label: 'Fallback',           cls: 'border-faint/55 bg-faint/10 text-faint' },
  NO_BLOCK:         { label: 'No block',           cls: 'border-ok/55 bg-ok/10 text-ok' },
};

function HardPolicyMessage({ d }) {
  if (d.hard_policy_would_block === false && d.final_decision !== 'ALLOW') {
    return (
      <p className="flex items-start gap-2 rounded-xl border border-info/45 bg-info/10
                    px-3 py-2 text-[11px] leading-relaxed text-info" role="status">
        <Brain size={13} className="mt-px shrink-0" aria-hidden="true" />
        <span>
          <b>Hard rules passed</b> — AI supplied the differentiating signal.
        </span>
      </p>
    );
  }
  if (d.hard_policy_would_block === true) {
    return (
      <p className="flex items-start gap-2 rounded-xl border border-bad/45 bg-bad/10
                    px-3 py-2 text-[11px] leading-relaxed text-bad" role="status">
        <ShieldX size={13} className="mt-px shrink-0" aria-hidden="true" />
        <span>
          <b>Known policy violation</b> — deterministic control blocked the action.
        </span>
      </p>
    );
  }
  return null;
}

function AiModeMessage({ mode }) {
  if (mode === 'observe') {
    return (
      <p className="flex items-start gap-2 rounded-xl border border-warn/45 bg-warn/10
                    px-3 py-2 text-[11px] leading-relaxed text-warn" role="status">
        <Eye size={13} className="mt-px shrink-0" aria-hidden="true" />
        <span>AI observed this event but did not control enforcement.</span>
      </p>
    );
  }
  return null;
}

function DegradedWarning({ degraded }) {
  if (!degraded) return null;
  return (
    <p className="flex items-start gap-2 rounded-xl border border-warn/45 bg-warn/10
                  px-3 py-2 text-[11px] leading-relaxed text-warn" role="alert">
      <AlertTriangle size={13} className="mt-px shrink-0" aria-hidden="true" />
      <span>
        <b>Model degraded or unavailable.</b> Decisions may rely on deterministic policy alone.
      </span>
    </p>
  );
}

export default function AiIntelligencePanel({ event }) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const d = normalizeDecisionIntelligence(event);
  if (!d) return null;

  const src = d.decision_source;
  const badge = src ? SOURCE_BADGE[src] : null;

  return (
    <section className="card p-3.5 space-y-2.5" aria-label="AI intelligence">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-[13.5px]">
          <Shield size={13} className="text-info" aria-hidden="true" />
          AI Intelligence
        </h2>
        {badge && (
          <span className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5
                            text-[10px] font-bold tracking-[.1em] ${badge.cls}`}
            aria-label={`Decision source: ${badge.label}`}>
            {badge.label.toUpperCase()}
          </span>
        )}
      </div>

      <HardPolicyMessage d={d} />
      <AiModeMessage mode={d.ai_mode} />
      <DegradedWarning degraded={d.model_degraded} />

      {/* Stacked evidence summary */}
      <dl className="grid grid-cols-2 gap-1 font-mono text-[10px]">
        {[
          ['Decision source', d.decision_source?.replace(/_/g, ' ')],
          ['Final decision', d.final_decision],
          ['AI operating mode', d.ai_mode],
          ['Model', d.anomaly_model],
          ['Model version', d.anomaly_model_version],
          ['Artifact verified', d.artifact_verified != null ? String(d.artifact_verified) : null],
          ['Policy version', d.policy_version],
          ['Incident ID', d.incident_id],
          ['Response playbook', d.response_playbook?.replace(/_/g, ' ')],
        ].filter(([, v]) => v != null).map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-1 rounded-md
                                      border border-line bg-sunken/70 px-1.5 py-0.5">
            <dt className="truncate text-faint">{label}</dt>
            <dd className="shrink-0 tabular-nums text-dim">{value}</dd>
          </div>
        ))}
      </dl>

      {/* model_confidence: null → never rendered as a percentage */}
      {d.model_confidence != null && (
        <p className="font-mono text-[10px] text-faint">
          Model confidence: {(d.model_confidence * 100).toFixed(1)}%
        </p>
      )}

      {/* Anomaly risk — labelled 'Anomaly risk', never 'probability' */}
      {d.anomaly_risk_score != null && (
        <RiskMeter risk={d.anomaly_risk_score} modelVersion={d.anomaly_model_version}
          unavailable={d.model_degraded} />
      )}

      {/* Hard-policy reasons */}
      {d.hard_policy_reasons.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {d.hard_policy_reasons.map((r, i) => (
            <span key={i} className="chip border-bad/45 bg-bad/10 text-bad text-[9.5px]">
              {String(r).replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      {/* Collapsible backend-supplied evidence */}
      {d.anomaly_features && Object.keys(d.anomaly_features).length > 0 && (
        <details open={evidenceOpen} onToggle={(e) => setEvidenceOpen(e.currentTarget.open)}>
          <summary className="label mb-1 cursor-pointer select-none"
            aria-label="Toggle technical evidence">
            <span className="inline-flex items-center gap-1">
              <ChevronDown size={9} className={`transition-transform ${evidenceOpen ? 'rotate-0' : '-rotate-90'}`}
                aria-hidden="true" />
              Backend-supplied features
            </span>
          </summary>
          <dl className="grid grid-cols-2 gap-1 font-mono text-[9.5px]">
            {Object.entries(d.anomaly_features).map(([k, val]) => (
              <div key={k} className="flex items-baseline justify-between gap-1 rounded-md
                                      border border-line bg-sunken/70 px-1.5 py-0.5">
                <dt className="truncate text-faint">{FEATURE_LABELS[k] ?? k}</dt>
                <dd className="shrink-0 tabular-nums text-dim">{Number(val)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  );
}
