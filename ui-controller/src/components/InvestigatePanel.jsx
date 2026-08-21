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
    <section className="card pane flex flex-col p-3.5" aria-label="Incident investigation">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-[13.5px]">
          <Bot size={13} className="text-violet" aria-hidden="true" />Investigator
        </h2>
        <button onClick={run} disabled={busy} className="btn btn-sm">
          {busy ? <Loader2 size={11} className="animate-spin" aria-hidden="true" />
                : <Search size={11} aria-hidden="true" />}
          {busy ? 'Working' : 'Run'}
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-bad/45 bg-bad/10 px-2 py-1 font-mono text-[10px] text-bad">
          {error}
        </p>
      )}
      {!report && !error && (
        <p className="text-[11.5px] text-faint">Read-only agent over the latest incident.</p>
      )}

      {report && (
        <div className="space-y-2">
          {/* The agent's own guardrail, surfaced rather than hidden. */}
          {report.disallowed?.length > 0 && (
            <p className="flex items-start gap-1.5 rounded-lg border border-ok/45 bg-ok/10 px-2 py-1
                          text-[10px] text-ok">
              <Ban size={11} className="mt-px shrink-0" aria-hidden="true" />
              Cannot act on the robot: {report.disallowed.join(', ').replace(/_/g, ' ')}
            </p>
          )}
          {report.tools_used?.length > 0 && (
            <div>
              <span className="label mb-1">Tools used</span>
              <div className="flex flex-wrap gap-1">
                {report.tools_used.map((t) => (
                  <span key={t} className="chip text-[9.5px]">{t.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
          )}
          {report.report?.recommendations?.length > 0 && (
            <div>
              <span className="label mb-1">Recommended</span>
              <ul className="space-y-0.5 text-[10.5px] text-dim">
                {report.report.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-1.5">
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
