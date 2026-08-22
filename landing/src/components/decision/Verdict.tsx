import { AnimatePresence, motion } from 'framer-motion';
import type { Outcome, Scenario } from '../../data/demoData';
import { Chip, statusTone, type Tone } from '../ui/Primitives';
import { useReducedMotion } from '../../hooks/useMotionPrefs';

const outcomeTone: Record<Outcome, Tone> = {
  ALLOW: 'allow',
  ALLOW_CONSTRAINED: 'warn',
  DENY: 'deny',
  ESTOP: 'deny',
};

const shell: Record<Tone, string> = {
  neutral: 'border-hairline bg-surface-2/60',
  cyan: 'border-cyan/40 bg-cyan/6',
  allow: 'border-allow/45 bg-allow/8',
  warn: 'border-warn/45 bg-warn/8',
  deny: 'border-deny/55 bg-deny/10',
};

const label: Record<Tone, string> = {
  neutral: 'text-ink',
  cyan: 'text-cyan',
  allow: 'text-allow',
  warn: 'text-warn',
  deny: 'text-deny',
};

/** Final verdict + containment actions for a scenario run. */
export function Verdict({ scenario, active }: { scenario: Scenario; active: boolean }) {
  const reduced = useReducedMotion();
  const tone = outcomeTone[scenario.outcome];
  const isEstop = scenario.outcome === 'ESTOP';

  return (
    <AnimatePresence mode="wait">
      {active ? (
        <motion.div
          key={scenario.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduced ? 0 : 0.4, ease: [0.22, 1, 0.36, 1] }}
          className={`relative overflow-hidden rounded-lg border p-5 ${shell[tone]}`}
        >
          {/* One restrained pulse on E-STOP, not a strobe. */}
          {isEstop && !reduced && (
            <motion.span
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 bg-deny/22"
              initial={{ opacity: 0.9 }}
              animate={{ opacity: 0 }}
              transition={{ duration: 1.1, ease: 'easeOut' }}
            />
          )}

          <div className="relative flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-mono text-[10px] tracking-[0.16em] text-ink-faint">OUTCOME</span>
            <span
              className={`font-mono text-lg font-semibold tracking-[0.06em] ${label[tone]}`}
            >
              {scenario.outcomeLabel}
            </span>
            <span className="ml-auto tabnum font-mono text-[11px] text-ink-faint">
              {scenario.latencyMs} ms
            </span>
          </div>

          {scenario.note && (
            <p className="relative mt-3 text-[13.5px] leading-relaxed text-ink">{scenario.note}</p>
          )}

          <div className="relative mt-4 flex flex-wrap gap-1.5">
            {scenario.policyReasons.map((r) => (
              <Chip key={r.code} tone={statusTone(r.status)}>
                {r.code}
              </Chip>
            ))}
          </div>

          {scenario.containment.length > 0 && (
            <div className="relative mt-4 border-t border-hairline-strong/70 pt-4">
              <p className="mb-2.5 font-mono text-[10px] tracking-[0.14em] text-ink-faint">
                CONTAINMENT
              </p>
              <ul className="space-y-1.5">
                {scenario.containment.map((c, i) => (
                  <motion.li
                    key={c}
                    initial={reduced ? false : { opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: reduced ? 0 : 0.15 + i * 0.18, duration: 0.3 }}
                    className="flex items-center gap-2 font-mono text-[11.5px] text-ink"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                      <path
                        d="M2 6.4 4.7 9 10 3.2"
                        stroke="currentColor"
                        className={label[tone]}
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    {c}
                  </motion.li>
                ))}
              </ul>
            </div>
          )}
        </motion.div>
      ) : (
        <motion.div
          key="pending"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="rounded-lg border border-dashed border-hairline-strong bg-surface-2/30 p-5"
        >
          <p className="font-mono text-[11px] tracking-[0.14em] text-ink-faint">
            EVALUATING COMMAND…
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
