import { useState } from 'react';
import { Ban, Bot, Loader2, Search } from 'lucide-react';
import { investigate } from '../lib/omniguard.js';

export default function InvestigatePanel({ cfg }) {
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    setBusy(true);
    try { setReport(await investigate(cfg)); setError(null); }
    catch (e) { setError(String(e.message ?? e)); }
    finally { setBusy(false); }
  };

  return (
    <section className="card p-4" aria-label="Incident investigation">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[15px]">
          <Bot size={15} className="text-info" aria-hidden="true" />Investigator
        </h2>
        <button onClick={run} disabled={busy} className="btn px-3 py-1.5 text-[12px]">
          {busy ? <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                : <Search size={13} aria-hidden="true" />}
          {busy ? 'Working' : 'Investigate'}
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-bad/50 bg-bad/10 px-3 py-2 font-mono text-[11px] text-bad">{error}</p>
      )}

      {!report && !error && (
        <p className="text-[12px] text-faint">
          Runs the read-only incident agent against the latest event.
        </p>
      )}

      {report && (
        <div className="space-y-3">
          {/* The agent's own guardrail, surfaced rather than hidden. */}
          {report.disallowed?.length > 0 && (
            <p className="flex items-center gap-2 rounded-xl border border-ok/50 bg-ok/10 px-3 py-2 text-[11.5px] text-ok">
              <Ban size={13} className="shrink-0" aria-hidden="true" />
              Cannot act on the robot: {report.disallowed.join(', ').replace(/_/g, ' ')}
            </p>
          )}

          {report.tools_used?.length > 0 && (
            <div>
              <span className="label mb-1.5">Tools used</span>
              <div className="flex flex-wrap gap-1.5">
                {report.tools_used.map((t) => (
                  <span key={t} className="rounded-full border border-line bg-sunken/70 px-2.5 py-0.5
                                           font-mono text-[10.5px] text-dim">{t.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
          )}

          {report.report?.recommendations?.length > 0 && (
            <div>
              <span className="label mb-1.5">Recommended</span>
              <ul className="space-y-1 text-[11.5px] text-dim">
                {report.report.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-faint" aria-hidden="true">·</span>
                    <span>{typeof r === 'string' ? r : JSON.stringify(r)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
