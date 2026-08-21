import { motion } from 'framer-motion';
import type { Scenario } from '../../data/demoData';
import { statusTone, toneText } from '../ui/Primitives';
import { useReducedMotion } from '../../hooks/useMotionPrefs';

const dotBg = {
  neutral: 'bg-ink-faint',
  cyan: 'bg-cyan',
  allow: 'bg-allow',
  warn: 'bg-warn',
  deny: 'bg-deny',
} as const;

/**
 * Six-stage authorization trace. Stages transition
 * pending → evaluated → allowed/denied as the run progresses.
 */
export function DecisionTrace({
  scenario,
  revealed,
}: {
  scenario: Scenario;
  revealed: number;
}) {
  const reduced = useReducedMotion();

  return (
    <ol className="relative space-y-0" aria-live="polite">
      {scenario.stages.map((stage, i) => {
        const done = i < revealed;
        const tone = statusTone(stage.status);
        const isLast = i === scenario.stages.length - 1;

        return (
          <li key={stage.label} className="relative flex gap-3.5 pb-5 last:pb-0">
            {/* Rail */}
            {!isLast && (
              <span
                aria-hidden="true"
                className={`absolute left-[5px] top-4 h-[calc(100%-0.5rem)] w-px transition-colors duration-500 ${
                  done ? 'bg-hairline-strong' : 'bg-hairline/60'
                }`}
              />
            )}

            <span className="relative mt-1 flex h-[11px] w-[11px] shrink-0 items-center justify-center">
              <motion.span
                className={`h-[11px] w-[11px] rounded-full ${done ? dotBg[tone] : 'bg-surface-3'}`}
                initial={false}
                animate={{ scale: done ? 1 : 0.6 }}
                transition={{ duration: reduced ? 0 : 0.3, ease: [0.22, 1, 0.36, 1] }}
              />
            </span>

            <motion.div
              className="min-w-0 flex-1"
              initial={false}
              animate={{ opacity: done ? 1 : 0.35 }}
              transition={{ duration: reduced ? 0 : 0.3 }}
            >
              <p
                className={`text-[13.5px] font-medium leading-tight ${done ? 'text-ink' : 'text-ink-faint'}`}
              >
                {stage.label}
              </p>
              <p
                className={`mt-1 break-words font-mono text-[11px] leading-relaxed ${
                  done ? toneText[tone] : 'text-ink-faint'
                }`}
              >
                {done ? stage.detail : 'pending…'}
              </p>
            </motion.div>
          </li>
        );
      })}
    </ol>
  );
}
