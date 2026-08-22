import { useEffect, useState } from 'react';
import { FlaskConical, Loader2, Play } from 'lucide-react';
import { listScenarios, runScenario } from '../lib/omniguard.js';

/* Scenario runs inject a server-side BehaviorContext override, so their verdicts
 * are clean and repeatable — this is the reliable demo path. */
export default function ScenarioPanel({ cfg, onResult }) {
  const [scenarios, setScenarios] = useState([]);
  const [busy, setBusy] = useState(null);
  const [protection, setProtection] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    listScenarios(cfg)
      .then((s) => alive && (setScenarios(s), setError(null)))
      .catch((e) => alive && setError(String(e.message ?? e)));
    return () => { alive = false; };
  }, [cfg]);

  const run = async (id) => {
    setBusy(id);
    try { onResult(await runScenario(cfg, id, { protection })); setError(null); }
    catch (e) { setError(String(e.message ?? e)); }
    finally { setBusy(null); }
  };

  return (
    <section className="card pane flex flex-col p-3.5" aria-label="Scenarios">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-[13.5px]">
          <FlaskConical size={13} className="text-info" aria-hidden="true" />Scenarios
        </h2>
        <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-line
                          bg-sunken/70 px-2 py-1 text-[10px] text-dim">
          <input type="checkbox" checked={protection} className="size-3 cursor-pointer accent-[#059669]"
            onChange={(e) => setProtection(e.target.checked)} />
          Protection {protection ? 'ON' : 'OFF'}
        </label>
      </div>

      {error && (
        <p className="mb-2 rounded-lg border border-bad/45 bg-bad/10 px-2 py-1 font-mono
                      text-[10px] text-bad">{error}</p>
      )}

      <div className="grid gap-1.5">
        {scenarios.length === 0 && !error
          ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="a-shimmer h-7 rounded-lg border border-line bg-sunken/70" />
            ))
          : scenarios.map((s) => (
              <button key={s.id} onClick={() => run(s.id)} disabled={busy !== null}
                title={s.label || s.description || s.id}
                className="btn btn-sm justify-start">
                {busy === s.id
                  ? <Loader2 size={11} className="shrink-0 animate-spin text-info" aria-hidden="true" />
                  : <Play size={11} className="shrink-0 text-faint" aria-hidden="true" />}
                <span className="truncate capitalize">{s.id.replace(/_/g, ' ')}</span>
              </button>
            ))}
      </div>
    </section>
  );
}
