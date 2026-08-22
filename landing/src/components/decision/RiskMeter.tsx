import { motion } from 'framer-motion';
import { useReducedMotion } from '../../hooks/useMotionPrefs';

/** Behavioral risk score, 0–1. Colour and label both encode severity. */
export function RiskMeter({ value, active }: { value: number; active: boolean }) {
  const reduced = useReducedMotion();
  const pct = Math.round(value * 100);

  const band =
    value >= 0.8
      ? { label: 'CRITICAL', color: 'var(--color-deny)', text: 'text-deny' }
      : value >= 0.5
        ? { label: 'ELEVATED', color: 'var(--color-warn)', text: 'text-warn' }
        : { label: 'NOMINAL', color: 'var(--color-allow)', text: 'text-allow' };

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="font-mono text-[10px] tracking-[0.14em] text-ink-faint">
          AI BEHAVIORAL RISK
        </span>
        <span className={`font-mono text-[11px] font-semibold tracking-[0.1em] ${band.text}`}>
          {band.label}
        </span>
      </div>

      <div
        className="relative h-2 w-full overflow-hidden rounded-full bg-surface-3"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`AI behavioral risk score ${value.toFixed(2)} of 1.00, ${band.label.toLowerCase()}`}
      >
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: band.color }}
          initial={{ width: 0 }}
          animate={{ width: active ? `${pct}%` : 0 }}
          transition={{ duration: reduced ? 0 : 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
        {/* Hard-policy threshold marker at 0.80. */}
        <span
          aria-hidden="true"
          className="absolute inset-y-0 w-px bg-ink-faint/50"
          style={{ left: '80%' }}
        />
      </div>

      <div className="mt-2 flex items-baseline justify-between">
        <span className={`tabnum font-mono text-2xl font-semibold ${band.text}`}>
          {active ? value.toFixed(2) : 'N/A'}
        </span>
        <span className="font-mono text-[10px] text-ink-faint">threshold 0.80</span>
      </div>
    </div>
  );
}
