import { Brain, ChevronRight, Scale, ShieldCheck, ShieldX } from 'lucide-react';
import RiskMeter from './RiskMeter.jsx';
import AiIntelligencePanel from './AiIntelligencePanel.jsx';
import { classifyDecisionSource, FEATURE_LABELS } from '../lib/omniguard.js';

const VERDICT = {
  ALLOW: { Icon: ShieldCheck, cls: 'border-ok/55 bg-ok/10 text-ok' },
  HOLD:  { Icon: Scale,       cls: 'border-warn/55 bg-warn/10 text-warn' },
  BLOCK: { Icon: ShieldX,     cls: 'border-bad/55 bg-bad/10 text-bad' },
};

const SOURCE_LABEL = {
  HARD_POLICY:      'HARD POLICY',
  ACTION_WINDOW_AI: 'ACTION-WINDOW AI',
  AI_WARNING:       'AI WARNING',
  FALLBACK:         'FALLBACK',
  NO_BLOCK:         'NO BLOCK',
};

const SOURCE_CLS = {
  HARD_POLICY:      'border-bad/55 bg-bad/10 text-bad',
  ACTION_WINDOW_AI: 'border-info/55 bg-info/10 text-info',
  AI_WARNING:       'border-warn/55 bg-warn/10 text-warn',
  FALLBACK:         'border-faint/55 bg-faint/10 text-faint',
  NO_BLOCK:         'border-ok/55 bg-ok/10 text-ok',
};

/** Stacked evidence row for the strongest AI scenario. */
function EvidenceRow({ label, value, tone }) {
  return (
    <div className="flex items-baseline justify-between gap-2 font-mono text-[10px]">
      <span className="text-faint">{label}</span>
      <span className={tone ?? 'text-dim'}>{value}</span>
    </div>
  );
}

export default function DecisionCard({ event, timeline }) {
  if (!event) {
    return (
      <section className="card flex flex-col p-3.5" aria-label="Latest decision">
        <h2 className="text-[13.5px]">Latest decision</h2>
        <p className="mt-2 text-[11.5px] text-faint">
          Run a scenario or move a stick to produce a verdict.
        </p>
      </section>
    );
  }

  const v = VERDICT[event.final_decision] ?? VERDICT.HOLD;
  const { Icon } = v;
  /* hard_policy_would_block === false on a BLOCK is the whole thesis: the rules
   * alone would have allowed it and only the model caught it. */
  const aiOnly = event.hard_policy_would_block === false && event.final_decision !== 'ALLOW';
  const decisionSrc = classifyDecisionSource(event);

  return (
    <section className="card pane flex flex-col p-3.5" aria-label="Latest decision">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[13.5px]">Latest decision</h2>
        <div className="flex items-center gap-1.5">
          {/* Decision-source badge */}
          {decisionSrc && (
            <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5
                              text-[9px] font-bold tracking-[.08em]
                              ${SOURCE_CLS[decisionSrc] ?? ''}`}>
              {SOURCE_LABEL[decisionSrc] ?? decisionSrc}
            </span>
          )}
          <span className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5
                            text-[10px] font-bold tracking-[.1em] ${v.cls}`}>
            <Icon size={11} aria-hidden="true" />{event.final_decision}
          </span>
        </div>
      </div>

      {/* Stacked evidence summary for decision-source visualization */}
      {(event.credential_status || event.device_status || event.zone_status ||
        event.hard_policy_would_block != null || event.anomaly_risk_score != null) && (
        <div className="mb-2 space-y-0.5 rounded-xl border border-line bg-sunken/70 px-3 py-2">
          {event.credential_status && (
            <EvidenceRow label="Credential" value={event.credential_status}
              tone={event.credential_status === 'VALID' ? 'text-ok' : 'text-bad'} />
          )}
          {event.device_status && (
            <EvidenceRow label="Device" value={event.device_status}
              tone={event.device_status === 'KNOWN' ? 'text-ok' : 'text-bad'} />
          )}
          {event.zone_status && (
            <EvidenceRow label="Zone" value={event.zone_status}
              tone={event.zone_status === 'ALLOWED' ? 'text-ok' : 'text-bad'} />
          )}
          {event.hard_policy_would_block != null && (
            <EvidenceRow label="Hard rules"
              value={event.hard_policy_would_block ? 'FAIL' : 'PASS'}
              tone={event.hard_policy_would_block ? 'text-bad' : 'text-ok'} />
          )}
          {event.anomaly_risk_score != null && (
            <EvidenceRow label="Action-window risk"
              value={event.anomaly_risk_score.toFixed(2)}
              tone={event.anomaly_risk_score >= 0.8 ? 'text-bad'
                    : event.anomaly_risk_score >= 0.6 ? 'text-warn' : 'text-ok'} />
          )}
          {event.caught_by && (
            <EvidenceRow label="Caught by"
              value={String(event.caught_by).replace(/_/g, ' ')}
              tone={aiOnly ? 'text-info' : 'text-bad'} />
          )}
          <EvidenceRow label="Decision" value={event.final_decision}
            tone={v.cls.includes('ok') ? 'text-ok' : v.cls.includes('bad') ? 'text-bad' : 'text-warn'} />
        </div>
      )}

      <div className="mb-2 flex flex-wrap gap-1">
        <span className="chip">{event.policy_decision}</span>
        {event.caught_by && (
          <span className={`chip ${aiOnly ? 'border-info/55 bg-info/10 text-info' : ''}`}>
            {aiOnly && <Brain size={9} aria-hidden="true" />}
            caught by {String(event.caught_by).replace(/_/g, ' ')}
          </span>
        )}
        {event.reasons?.map((r) => (
          <span key={r} className="chip border-bad/45 bg-bad/10 text-bad">{r}</span>
        ))}
      </div>

      <RiskMeter risk={event.anomaly_risk_score} modelVersion={event.anomaly_model_version}
        unavailable={event.ai_unavailable} />

      <div className="mt-2.5">
        <span className="label mb-1">Server-derived behaviour</span>
        <dl className="grid grid-cols-2 gap-1 font-mono text-[9.5px]">
          {Object.entries(event.anomaly_features ?? {}).map(([k, val]) => (
            <div key={k} className="flex items-baseline justify-between gap-1 rounded-md
                                    border border-line bg-sunken/70 px-1.5 py-0.5">
              <dt className="truncate text-faint">{FEATURE_LABELS[k] ?? k}</dt>
              <dd className="shrink-0 tabular-nums text-dim">{Number(val)}</dd>
            </div>
          ))}
        </dl>
      </div>

      {timeline?.length > 0 && (
        <div className="mt-2.5">
          <span className="label mb-1">Decision trace</span>
          <ol className="space-y-0.5">
            {[...timeline].reverse().map((step, i) => (
              <li key={`${step.step}-${i}`}
                className="flex items-center gap-1 font-mono text-[9.5px] text-dim">
                <ChevronRight size={9} className="shrink-0 text-faint" aria-hidden="true" />
                <span className="truncate">{step.step.replace(/_/g, ' ')}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {event.incident_explanation?.summary && (
        <p className="mt-2.5 rounded-lg border border-line bg-sunken/70 px-2.5 py-1.5
                      text-[10.5px] leading-relaxed text-dim">
          {event.incident_explanation.summary}
        </p>
      )}

      {/* Embedded AI Intelligence panel for events with AI decision intelligence */}
      {(event.decision_source || event.hard_policy_would_block != null) && (
        <div className="mt-2.5">
          <AiIntelligencePanel event={event} />
        </div>
      )}
    </section>
  );
}

