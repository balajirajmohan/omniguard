import { useEffect, useState } from 'react';
import type { Scenario } from '../../data/demoData';
import { useReducedMotion } from '../../hooks/useMotionPrefs';

const STAGE_MS = 480;

/**
 * Steps a scenario's decision trace from `Command received` through
 * `Containment confirmed`. Under reduced motion the full trace is revealed at
 * once so no information depends on animation.
 *
 * This hook intentionally drives the scripted product preview. Live operations
 * are handled by the separately deployed operations console.
 */
export function useScenarioRun(scenario: Scenario, runKey: number = 0) {
  const reduced = useReducedMotion();
  const total = scenario.stages.length;
  const [revealed, setRevealed] = useState(reduced ? total : 0);

  useEffect(() => {
    if (reduced) {
      setRevealed(total);
      return;
    }
    setRevealed(0);
    let n = 0;
    const id = window.setInterval(() => {
      n += 1;
      setRevealed(n);
      if (n >= total) window.clearInterval(id);
    }, STAGE_MS);
    return () => window.clearInterval(id);
    // `runKey` lets a caller replay the same scenario from the start.
  }, [scenario.id, total, reduced, runKey]);

  return {
    revealed,
    /** True once the verdict stage has been reached. */
    settled: revealed >= total - 1,
    complete: revealed >= total,
  };
}
