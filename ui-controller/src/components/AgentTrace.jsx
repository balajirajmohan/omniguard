import { Bot, CheckCircle2, ChevronRight, XCircle } from 'lucide-react';
import { normalizeAgentTrace } from '../lib/omniguard.js';

const clock = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleTimeString([], { hour12: false }); } catch { return '—'; }
};

/**
 * Agent investigation timeline.
 *
 * Displays each validated agent step: tool, timing, result, error.
 *
 * CRITICAL: "Proposed" until deterministic containment confirms execution.
 * Never implies the agent directly controlled the robot.
 */
export default function AgentTrace({ raw }) {
  const trace = normalizeAgentTrace(raw);
  if (!trace) return null;

  return (
    <div className="space-y-2.5">
      {/* Agent metadata */}
      <dl className="flex flex-wrap gap-1.5">
        {trace.agent_mode && (
          <span className="chip text-[9.5px]">mode: {trace.agent_mode}</span>
        )}
        {trace.provider && (
          <span className="chip text-[9.5px]">provider: {trace.provider}</span>
        )}
        {trace.model && (
          <span className="chip text-[9.5px]">model: {trace.model}</span>
        )}
        {trace.fallback_used && (
          <span className="chip border-warn/45 bg-warn/10 text-warn text-[9.5px]"
            aria-label="Deterministic fallback agent was used">
            DETERMINISTIC FALLBACK
          </span>
        )}
      </dl>

      {/* Tool call timeline */}
      {trace.steps.length > 0 && (
        <ol className="space-y-1" aria-label="Agent tool calls">
          {trace.steps.map((step, i) => (
            <li key={i} className="flex items-start gap-2 rounded-lg border border-line
                                   bg-sunken/70 px-2.5 py-1.5">
              <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center
                               rounded-full bg-elevated font-mono text-[8px] text-faint">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <Bot size={10} className="shrink-0 text-violet" aria-hidden="true" />
                  <span className="font-mono text-[10.5px] text-dim">
                    {step.tool?.replace(/_/g, ' ') ?? 'unknown tool'}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 font-mono text-[9px] text-faint">
                  {step.start_time && <span>{clock(step.start_time)}</span>}
                  {step.start_time && step.end_time && (
                    <ChevronRight size={8} className="text-faint" aria-hidden="true" />
                  )}
                  {step.end_time && <span>{clock(step.end_time)}</span>}
                </div>
                {step.result_summary && (
                  <p className="mt-0.5 text-[10px] text-dim">{step.result_summary}</p>
                )}
                {step.error && (
                  <p className="mt-0.5 flex items-center gap-1 text-[10px] text-bad">
                    <XCircle size={9} aria-hidden="true" />
                    {step.error}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}

      {/* Tools used summary */}
      {trace.tools_used.length > 0 && (
        <div>
          <span className="label mb-1">Tools used</span>
          <div className="flex flex-wrap gap-1">
            {trace.tools_used.map((t) => (
              <span key={t} className="chip text-[9.5px]">{t.replace(/_/g, ' ')}</span>
            ))}
          </div>
        </div>
      )}

      {/* Proposed playbook — explicitly NOT labelled as executed */}
      {trace.proposed_playbook && (
        <div className="flex items-start gap-2 rounded-xl border border-warn/45 bg-warn/10
                        px-3 py-2">
          <CheckCircle2 size={13} className="mt-px shrink-0 text-warn" aria-hidden="true" />
          <div>
            <p className="text-[11px] font-semibold text-warn">
              {trace.execution_authorized ? 'Authorized' : 'Proposed'} playbook
            </p>
            <p className="mt-0.5 font-mono text-[10.5px] text-dim">
              {trace.proposed_playbook.replace(/_/g, ' ')}
            </p>
            {!trace.execution_authorized && (
              <p className="mt-1 text-[9.5px] text-faint">
                Proposed by the agent. Not executed until deterministic containment confirms.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
