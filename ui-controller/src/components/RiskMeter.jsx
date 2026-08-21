import { RISK_CRITICAL, RISK_WARNING, riskBand } from '../lib/omniguard.js';

const TONE = {
  normal:   { bar: 'bg-ok',   text: 'text-ok',   word: 'NORMAL' },
  warning:  { bar: 'bg-warn', text: 'text-warn', word: 'ELEVATED' },
  critical: { bar: 'bg-bad',  text: 'text-bad',  word: 'CRITICAL' },
};

export default function RiskMeter({ risk, modelVersion, unavailable }) {
  const value = typeof risk === 'number' ? risk : 0;
  const tone = TONE[riskBand(value)];

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="label">AI anomaly risk</span>
        <span className={`font-mono text-[11px] font-bold ${tone.text}`}>
          {tone.word}{unavailable ? ' · MODEL UNAVAILABLE' : ''}
        </span>
      </div>

      <div className="relative h-2.5 overflow-hidden rounded-full bg-sunken ring-1 ring-line">
        <div className={`h-full rounded-full transition-[width] duration-500 ease-out ${tone.bar}`}
          style={{ width: `${Math.round(value * 100)}%` }} />
        {/* Threshold ticks: the numbers the decision actually turns on. */}
        {[RISK_WARNING, RISK_CRITICAL].map((t) => (
          <span key={t} className="absolute top-0 h-full w-px bg-white/45" style={{ left: `${t * 100}%` }} />
        ))}
      </div>

      <div className="mt-1 flex justify-between font-mono text-[10px] text-faint">
        <span className={tone.text}>{value.toFixed(2)}</span>
        <span>hold {RISK_WARNING} · block {RISK_CRITICAL}</span>
        {modelVersion && <span>{modelVersion}</span>}
      </div>
    </div>
  );
}
