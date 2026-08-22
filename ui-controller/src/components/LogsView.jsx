import { useMemo, useState } from 'react';
import { Download, FileJson, FileSpreadsheet, Radio, Trash2 } from 'lucide-react';
import {
  exportAllSessions, exportCsv, exportJson, exportSession, exportSessionCsv,
} from '../lib/useSessionLog.js';

const TONE = {
  ALLOW: 'text-ok', BLOCK: 'text-bad', HOLD: 'text-warn', BYPASS: 'text-warn', ERROR: 'text-bad',
};

const when = (iso) => {
  try { return new Date(iso).toLocaleString([], { hour12: false }); } catch { return iso ?? '—'; }
};
const clock = (iso) => {
  try { return new Date(iso).toLocaleTimeString([], { hour12: false }); } catch { return '—'; }
};

function EntryRow({ e }) {
  const decision = e.final_decision ?? e.decision ?? e.status ?? '—';
  return (
    <tr className="border-b border-line/60 last:border-0 align-top">
      <td className="py-1.5 pr-3 font-mono text-[10px] text-faint whitespace-nowrap">
        {clock(e.timestamp ?? e.recorded_at)}
      </td>
      <td className={`py-1.5 pr-3 font-mono text-[10px] font-bold ${TONE[decision] ?? 'text-dim'}`}>
        {decision}
      </td>
      <td className="py-1.5 pr-3 font-mono text-[10px] text-dim whitespace-nowrap">
        {e.device_id ?? '—'}
      </td>
      <td className="py-1.5 pr-3 font-mono text-[10px] text-dim whitespace-nowrap">
        {e.destination ?? '—'}{e.speed != null && ` @ ${e.speed}`}
      </td>
      <td className="py-1.5 pr-3 font-mono text-[10px] tabular-nums text-dim">
        {e.anomaly_risk_score ?? '—'}
      </td>
      <td className="py-1.5 font-mono text-[10px] text-dim">
        {(e.reasons ?? []).join(', ') || e.detail || '—'}
      </td>
    </tr>
  );
}

function EntryTable({ entries }) {
  if (!entries?.length) {
    return <p className="p-4 text-[12px] text-faint">No decisions recorded in this session.</p>;
  }
  return (
    <div className="pane max-h-full">
      <table className="w-full border-collapse">
        <thead className="sticky top-0 bg-surface/95 backdrop-blur">
          <tr className="border-b border-line">
            {['time', 'decision', 'device', 'target', 'risk', 'reasons'].map((h) => (
              <th key={h} className="py-1.5 pr-3 text-left label">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{[...entries].reverse().map((e, i) => <EntryRow key={i} e={e} />)}</tbody>
      </table>
    </div>
  );
}

export default function LogsView({ sessions, current, onRemove, onClearAll }) {
  /* The in-flight run is shown as a first-class session so nothing is invisible
   * until a reset happens. */
  const live = useMemo(() => ({
    id: '__live__', label: 'Current session', live: true,
    started_at: current[0]?.recorded_at, ended_at: null,
    entry_count: current.length, entries: current,
  }), [current]);

  const all = useMemo(() => [live, ...sessions], [live, sessions]);
  const [selectedId, setSelectedId] = useState('__live__');
  const selected = all.find((s) => s.id === selectedId) ?? live;

  return (
    <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[300px_1fr]">
      <section className="card pane flex flex-col p-3.5" aria-label="Sessions">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-[13.5px]">Sessions</h2>
          <div className="flex gap-1.5">
            <button className="btn btn-sm" disabled={!sessions.length}
              onClick={() => exportAllSessions(sessions)} title="Export every archived session">
              <Download size={11} aria-hidden="true" />All
            </button>
            <button className="btn btn-sm text-bad" disabled={!sessions.length}
              onClick={onClearAll} title="Delete all archived sessions">
              <Trash2 size={11} aria-hidden="true" />
            </button>
          </div>
        </div>

        <p className="mb-2 text-[10.5px] leading-relaxed text-faint">
          A session is archived automatically when you press <b className="text-dim">Reset demo</b>,
          so the run you just showed stays readable afterwards.
        </p>

        <ul className="space-y-1.5">
          {all.map((s) => {
            const on = s.id === selectedId;
            return (
              <li key={s.id}>
                <button onClick={() => setSelectedId(s.id)}
                  className={`w-full cursor-pointer rounded-xl border px-2.5 py-2 text-left transition-colors
                              ${on ? 'border-info/55 bg-info/10' : 'border-line bg-sunken/60 hover:border-line-hi'}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[11.5px] font-semibold">
                      {s.live && <Radio size={10} className="text-ok a-pulse" aria-hidden="true" />}
                      {s.live ? 'Current session' : when(s.started_at)}
                    </span>
                    <span className="font-mono text-[9.5px] text-faint">{s.entry_count}</span>
                  </div>
                  {!s.live && (
                    <span className="font-mono text-[9.5px] text-faint">ended {clock(s.ended_at)}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="card flex min-h-0 flex-col p-3.5" aria-label="Session detail">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-[13.5px]">
              {selected.live ? 'Current session' : `Session · ${when(selected.started_at)}`}
            </h2>
            <p className="font-mono text-[10px] text-faint">
              {selected.entries?.length ?? 0} decisions
              {selected.ended_at && ` · ended ${clock(selected.ended_at)}`}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button className="btn btn-sm" disabled={!selected.entries?.length}
              onClick={() => (selected.live
                ? exportCsv('current-decisions', selected.entries)
                : exportSessionCsv(selected))}>
              <FileSpreadsheet size={11} aria-hidden="true" />Decisions CSV
            </button>
            <button className="btn btn-sm" disabled={!selected.entries?.length}
              onClick={() => (selected.live
                ? exportJson('current-session', selected)
                : exportSession(selected))}>
              <FileJson size={11} aria-hidden="true" />Session JSON
            </button>
            {!selected.live && (
              <button className="btn btn-sm text-bad" onClick={() => {
                onRemove(selected.id);
                setSelectedId('__live__');
              }}>
                <Trash2 size={11} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
        <EntryTable entries={selected.entries} />
      </section>
    </div>
  );
}
