import { ArrowRight } from 'lucide-react';

const TONE = {
  ALLOW:  'text-ok',
  BLOCK:  'text-bad',
  HOLD:   'text-warn',
  BYPASS: 'text-warn',
  ERROR:  'text-bad',
};

export default function VerdictLog({ entries }) {
  return (
    <div className="mt-3">
      <span className="label mb-1.5">Decision history</span>
      <div className="h-[118px] overflow-y-auto rounded-xl border border-line bg-sunken/70 px-3 py-1">
        {entries.length === 0 ? (
          <p className="flex h-full items-center gap-1.5 font-mono text-[11px] text-faint">
            <ArrowRight size={11} aria-hidden="true" />awaiting first command
          </p>
        ) : (
          entries.map((e) => (
            <div key={e.id} className="a-rise flex gap-2.5 border-b border-line/60 py-1.5 last:border-0
                                       font-mono text-[11px]">
              <time className="shrink-0 text-faint tabular-nums">{e.time}</time>
              <span className={`shrink-0 font-bold ${TONE[e.decision] ?? 'text-dim'}`}>{e.decision}</span>
              <span className="truncate text-dim">{e.detail}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
