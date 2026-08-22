import { motion } from 'framer-motion';
import { ButtonLink } from '../components/ui/Button';
import { WarehouseScene } from '../components/scene/WarehouseScene';
import { useReducedMotion } from '../hooks/useMotionPrefs';

export function Hero() {
  const reduced = useReducedMotion();

  const rise = (delay: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: 20 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.65, delay, ease: [0.22, 1, 0.36, 1] as const },
        };

  return (
    <section id="platform" className="relative overflow-hidden pt-28 pb-16 sm:pt-32 lg:pt-36 lg:pb-24">
      {/* Ambient field: fine grid + a single restrained cyan wash. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="bg-grid mask-fade-edges absolute inset-0 opacity-70" />
        <div
          className="absolute -top-40 left-1/2 h-[560px] w-[900px] -translate-x-1/2 rounded-full opacity-45"
          style={{
            background:
              'radial-gradient(ellipse at center, rgba(34,211,238,0.16), rgba(34,211,238,0) 68%)',
          }}
        />
        <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-b from-transparent to-graphite" />
      </div>

      <div className="relative mx-auto grid w-full max-w-[1200px] grid-cols-1 items-start gap-12 px-5 sm:px-8 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-14">
        {/* ---- Copy ---- */}
        <div className="min-w-0 max-w-xl lg:pt-3">
          <motion.p
            {...rise(0)}
            className="mb-5 inline-flex items-center gap-2.5 rounded-full border border-cyan/25 bg-cyan/6 px-3.5 py-1.5 font-mono text-[10.5px] font-medium tracking-[0.16em] text-cyan"
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan" />
            RUNTIME SECURITY FOR PHYSICAL AI
          </motion.p>

          <motion.h1
            {...rise(0.08)}
            className="text-balance text-[2.15rem] font-semibold leading-[1.08] tracking-[-0.028em] text-ink sm:text-5xl lg:text-[3.4rem]"
          >
            Authorize every action{' '}
            <span className="relative">
              before a machine moves
              <span
                aria-hidden="true"
                className="absolute inset-x-0 -bottom-1 h-px bg-gradient-to-r from-cyan/70 via-cyan/25 to-transparent"
              />
            </span>
            .
          </motion.h1>

          <motion.p
            {...rise(0.16)}
            className="mt-6 max-w-[36rem] text-[15px] leading-relaxed text-ink-dim sm:text-[17px]"
          >
            OmniGuard combines machine identity, physical-context policy, behavioral AI, and active
            containment to stop compromised robot commands before cyber risk becomes a physical
            incident.
          </motion.p>

          <motion.div {...rise(0.24)} className="mt-8 flex flex-wrap items-center gap-3">
            <ButtonLink href="#how-it-works" variant="secondary" size="lg">
              See How It Works
            </ButtonLink>
          </motion.div>

          <motion.p
            {...rise(0.32)}
            className="mt-6 font-mono text-[11.5px] leading-relaxed text-ink-faint"
          >
            Built for autonomous fleets{' '}
            <span className="mx-1.5 text-hairline-strong">•</span> Demonstrated in NVIDIA Isaac Sim
          </motion.p>
        </div>

        {/* ---- Scene ---- */}
        <motion.div
          {...(reduced
            ? {}
            : {
                initial: { opacity: 0, scale: 0.97 },
                animate: { opacity: 1, scale: 1 },
                transition: { duration: 0.9, delay: 0.15, ease: [0.22, 1, 0.36, 1] as const },
              })}
          className="relative min-w-0"
        >
          <div className="rounded-2xl border border-hairline bg-surface/40 p-3 sm:p-4">
            <div className="mb-3 flex items-center gap-2 border-b border-hairline pb-3">
              <span className="font-mono text-[10px] tracking-[0.16em] text-ink-faint">
                WAREHOUSE_TWIN / SECTOR_04
              </span>
              <span className="ml-auto flex items-center gap-1.5 font-mono text-[10px] text-cyan">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan" />
                SIM
              </span>
            </div>
            <WarehouseScene />
          </div>
        </motion.div>
      </div>
    </section>
  );
}
