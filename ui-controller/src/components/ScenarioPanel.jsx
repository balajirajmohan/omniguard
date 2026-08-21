import { useEffect, useState } from 'react';
import { FlaskConical, Loader2, Play } from 'lucide-react';
import { listScenarios, runScenario } from '../lib/omniguard.js';

/* Scenario runs are the path the backend is actually tuned for: they inject a
 * BehaviorContext override, so verdicts are clean and repeatable. Ad-hoc
 * commands are scored against live server-derived timing instead. */
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
    try {
      onResult(await runScenario(cfg, id, { protection }));
      setError(null);
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setBusy(null);
    }
  };

  const pretty = (id) => id.replace(/_/g, ' ');

  return (
    <section className="card p-4" aria-label="Scenarios">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[15px]">
          <FlaskConical size={15} className="text-info" aria-hidden="true" />Scenarios
        </h2>
        <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-line
                          bg-sunken/70 px-2.5 py-1.5 text-[11px] text-dim">
          <input type="checkbox" checked={protection} className="size-3.5 cursor-pointer accent-[#059669]"
            onChange={(e) => setProtection(e.target.checked)} />
          Protection {protection ? 'ON' : 'OFF'}
        </label>
      </div>

      {error && (
        <p className="mb-2 rounded-lg border border-bad/50 bg-bad/10 px-3 py-2 font-mono text-[11px] text-bad">
          {error}
        </p>
      )}

      {scenarios.length === 0 && !error ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="a-shimmer h-9 rounded-xl border border-line bg-sunken/70" />
          ))}
        </div>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {scenarios.map((s) => {
            const id = s.id;
            const running = busy === id;
            return (
              <button key={id} onClick={() => run(id)} disabled={busy !== null}
                title={s.label || s.description || pretty(id)}
                className="btn justify-start px-3 py-2 text-[12px] font-medium disabled:opacity-50">
                {running
                  ? <Loader2 size={13} className="shrink-0 animate-spin text-info" aria-hidden="true" />
                  : <Play size={13} className="shrink-0 text-faint" aria-hidden="true" />}
                <span className="truncate capitalize">{pretty(id)}</span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
