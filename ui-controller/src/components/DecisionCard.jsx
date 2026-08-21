import { Brain, ChevronRight, Scale, ShieldCheck, ShieldX } from 'lucide-react';
import RiskMeter from './RiskMeter.jsx';
import { FEATURE_LABELS } from '../lib/omniguard.js';

const VERDICT = {
  ALLOW: { Icon: ShieldCheck, cls: 'border-ok/60 bg-ok/10 text-ok' },
  HOLD:  { Icon: Scale,       cls: 'border-warn/60 bg-warn/10 text-warn' },
  BLOCK: { Icon: ShieldX,     cls: 'border-bad/60 bg-bad/10 text-bad' },
};

/* "caught_by" is the whole thesis in one field: rules catch the known, the model
 * catches the unknown. hard_policy_would_block === false on a BLOCK means the
 * rules alone would have let it through. */
function CaughtBy({ event }) {
  const by = event.caught_by;
  if (!by) return null;
  const aiOnly = event.hard_policy_would_block === false && event.final_decision !== 'ALLOW';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5
                      font-mono text-[10.5px] ${aiOnly ? 'border-info/60 bg-info/10 text-info' : 'border-line text-dim'}`}>
      {aiOnly && <Brain size={10} aria-hidden="true" />}
      caught by {String(by).replace(/_/g, ' ')}
    </span>
  );
}

export default function DecisionCard({ event, timeline }) {
  if (!event) {
    return (
      <section className="card p-4" aria-label="Latest decision">
        <h2 className="mb-2 text-[15px]">Latest decision</h2>
        <p className="text-[12px] text-faint">Run a scenario or move a joystick to produce a verdict.</p>
      </section>
    );
  }

  const v = VERDICT[event.final_decision] ?? VERDICT.HOLD;
  const { Icon } = v;
  const features = event.anomaly_features ?? {};

  return (
    <section className="card p-4" aria-label="Latest decision">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[15px]">Latest decision</h2>
        <span className={`flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-bold
                          tracking-[.1em] ${v.cls}`}>
          <Icon size={13} aria-hidden="true" />{event.final_decision}
        </span>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <span className="rounded-full border border-line px-2.5 py-0.5 font-mono text-[10.5px] text-dim">
          {event.policy_decision}
        </span>
        <CaughtBy event={event} />
        {event.reasons?.map((r) => (
          <span key={r} className="rounded-full border border-bad/50 bg-bad/10 px-2.5 py-0.5
                                   font-mono text-[10.5px] text-bad">{r}</span>
        ))}
      </div>

      <RiskMeter risk={event.anomaly_risk_score} modelVersion={event.anomaly_model_version}
        unavailable={event.ai_unavailable} />

      {/* Server-derived features — why a HOLD happened, not just that it did. */}
      <div className="mt-3">
        <span className="label mb-1.5">Server-derived behaviour</span>
        <dl className="grid grid-cols-2 gap-1 font-mono text-[10.5px] sm:grid-cols-3">
          {Object.entries(features).map(([k, val]) => (
            <div key={k} className="flex items-baseline justify-between gap-2 rounded-lg
                                    border border-line bg-sunken/70 px-2 py-1">
              <dt className="truncate text-faint">{FEATURE_LABELS[k] ?? k}</dt>
              <dd className="shrink-0 tabular-nums text-dim">{Number(val)}</dd>
            </div>
          ))}
        </dl>
      </div>

      {timeline?.length > 0 && (
        <div className="mt-3">
          <span className="label mb-1.5">Decision trace</span>
          <ol className="space-y-0.5">
            {[...timeline].reverse().map((step, i) => (
              <li key={`${step.step}-${i}`} className="flex items-center gap-1.5 font-mono text-[10.5px] text-dim">
                <ChevronRight size={10} className="shrink-0 text-faint" aria-hidden="true" />
                <span className="truncate">{step.step.replace(/_/g, ' ')}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {event.incident_explanation?.summary && (
        <p className="mt-3 rounded-xl border border-line bg-sunken/70 px-3 py-2 text-[11.5px]
                      leading-relaxed text-dim">
          {event.incident_explanation.summary}
        </p>
      )}
    </section>
  );
}
