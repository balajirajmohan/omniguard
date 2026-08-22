import { Brain, Clock, ServerCrash, Sparkles, Timer } from 'lucide-react';
import { normalizeLlmProvenance } from '../lib/omniguard.js';

/* Visual states for the explanation. Never say "AI-generated" generically;
 * always identify the actual provider/model or label the fallback. */
const STATUS_LOOK = {
  live_llm:                { Icon: Sparkles,    word: 'Live LLM analysis',     cls: 'text-ok',    border: 'border-ok/45' },
  deterministic_fallback:  { Icon: Brain,       word: 'Deterministic fallback', cls: 'text-warn',  border: 'border-warn/45' },
  unavailable:             { Icon: ServerCrash, word: 'LLM unavailable',        cls: 'text-faint', border: 'border-faint/45' },
  pending:                 { Icon: Timer,       word: 'Analysis pending',       cls: 'text-info',  border: 'border-info/45' },
  failed:                  { Icon: ServerCrash, word: 'Analysis failed',        cls: 'text-bad',   border: 'border-bad/45' },
};

const clock = (iso) => {
  if (!iso) return null;
  try { return new Date(iso).toLocaleString([], { hour12: false }); } catch { return null; }
};

export default function IncidentExplanation({ raw }) {
  const p = normalizeLlmProvenance(raw);
  const look = STATUS_LOOK[p.status] ?? STATUS_LOOK.unavailable;
  const { Icon } = look;

  return (
    <div className="space-y-2.5">
      {/* Status badge */}
      <div className={`flex items-center gap-2 rounded-xl border ${look.border}
                       bg-sunken/70 px-3 py-2`} role="status">
        <Icon size={13} className={`shrink-0 ${look.cls}`} aria-hidden="true" />
        <span className={`text-[11px] font-semibold ${look.cls}`}>{look.word}</span>
        {p.provider && p.model && (
          <span className="ml-auto font-mono text-[9.5px] text-dim">
            {p.provider} / {p.model}
          </span>
        )}
        {p.fallback_used && !p.provider && (
          <span className="ml-auto font-mono text-[9.5px] text-warn">
            deterministic fallback agent
          </span>
        )}
      </div>

      {/* Fallback reason */}
      {p.fallback_used && p.fallback_reason && (
        <p className="text-[10.5px] text-faint">
          Fallback reason: {p.fallback_reason}
        </p>
      )}

      {/* Explanation body */}
      {[
        ['Operator summary', p.summary],
        ['Technical summary', p.technical_summary],
        ['Physical impact', p.physical_impact],
        ['Likely root cause', p.root_cause],
        ['Why suspicious', p.why_suspicious],
        ['Containment taken', p.containment_taken],
      ].filter(([, v]) => v).map(([label, value]) => (
        <div key={label}>
          <span className="label mb-0.5">{label}</span>
          <p className="rounded-lg border border-line bg-sunken/70 px-2.5 py-1.5
                        text-[10.5px] leading-relaxed text-dim">{value}</p>
        </div>
      ))}

      {/* Recommended actions */}
      {p.recommended_actions.length > 0 && (
        <div>
          <span className="label mb-1">Recommended actions</span>
          <ul className="space-y-0.5 text-[10.5px] text-dim">
            {p.recommended_actions.map((r, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="text-faint" aria-hidden="true">·</span>
                <span>{typeof r === 'string' ? r : JSON.stringify(r)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Provenance metadata */}
      <dl className="flex flex-wrap gap-1.5">
        {p.generated_at && (
          <span className="chip text-[9.5px]" title={p.generated_at}>
            <Clock size={9} aria-hidden="true" />
            {clock(p.generated_at)}
          </span>
        )}
        {p.latency_ms != null && (
          <span className="chip text-[9.5px]">
            <Timer size={9} aria-hidden="true" />
            {p.latency_ms}ms
          </span>
        )}
      </dl>
    </div>
  );
}
