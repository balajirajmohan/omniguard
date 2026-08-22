import { Brain, ChevronRight, Scale, ShieldCheck, ShieldX } from 'lucide-react';
import RiskMeter from './RiskMeter.jsx';
import { FEATURE_LABELS } from '../lib/omniguard.js';

const VERDICT = {
  ALLOW: { Icon: ShieldCheck, cls: 'border-ok/55 bg-ok/10 text-ok' },
  HOLD:  { Icon: Scale,       cls: 'border-warn/55 bg-warn/10 text-warn' },
  BLOCK: { Icon: ShieldX,     cls: 'border-bad/55 bg-bad/10 text-bad' },
};

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

  return (
    <section className="card pane flex flex-col p-3.5" aria-label="Latest decision">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[13.5px]">Latest decision</h2>
        <span className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5
                          text-[10px] font-bold tracking-[.1em] ${v.cls}`}>
          <Icon size={11} aria-hidden="true" />{event.final_decision}
        </span>
      </div>

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
    </section>
  );
}
