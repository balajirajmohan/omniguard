import type { ReactNode } from 'react';
import { Reveal } from '../components/ui/Reveal';
import { Chip, Section, SectionHeading } from '../components/ui/Primitives';
import { useReducedMotion } from '../hooks/useMotionPrefs';

interface Layer {
  step: string;
  kicker: string;
  title: string;
  body: string;
  chips: string[];
  icon: ReactNode;
}

const layers: Layer[] = [
  {
    step: '01',
    kicker: 'VERIFY',
    title: 'Machine identity and device trust',
    body: 'Validate signed credentials, delegated robot grants, controller binding, freshness, and replay protection.',
    chips: ['Credential verified', 'Controller binding matched', 'Robot grant confirmed'],
    icon: <KeyIcon />,
  },
  {
    step: '02',
    kicker: 'REASON',
    title: 'Policy plus behavioral AI',
    body: 'Evaluate destination, path, speed, live operating context, and deviations from a versioned behavioral baseline.',
    chips: ['Restricted destination', 'Speed above 1.5 m/s', 'Effective risk 0.92'],
    icon: <BrainIcon />,
  },
  {
    step: '03',
    kicker: 'CONTAIN',
    title: 'Stop the blast radius',
    body: 'Block unsafe commands, revoke credentials, quarantine identities, and request a robot base stop.',
    chips: ['Command blocked', 'Credential revoked', 'Base stop acknowledged'],
    icon: <StopIcon />,
  },
  {
    step: '04',
    kicker: 'INVESTIGATE',
    title: 'Explain and recover safely',
    body: 'Create a durable incident, then ask Sonnet asynchronously to explain evidence, physical impact, and recommended response. The LLM never controls the robot.',
    chips: ['INC-* created', 'Investigation pending', 'Human-approved recovery'],
    icon: <BrainIcon />,
  },
];

export function HowItWorks() {
  const reduced = useReducedMotion();

  return (
    <Section id="how-it-works">
      <Reveal>
        <SectionHeading
          eyebrow="HOW IT WORKS"
          title="One decision plane. Four accountable stages."
          body="Every command follows the same path. Deterministic checks run first, behavioral evidence is layered on top, containment is acknowledged, and investigation happens asynchronously."
        />
      </Reveal>

      <div className="relative mt-14">
        {/* Animated flow connecting the four cards. */}
        <div
          aria-hidden="true"
          className="absolute left-1/2 top-0 hidden h-px w-[calc(100%-8rem)] -translate-x-1/2 lg:block"
          style={{ top: '3.25rem' }}
        >
          <div className="h-px w-full bg-gradient-to-r from-transparent via-cyan/30 to-transparent" />
          {!reduced && (
            <div
              className="absolute -top-px h-px w-24 bg-gradient-to-r from-transparent via-cyan-bright to-transparent"
              style={{ animation: 'og-flow 4.5s linear infinite' }}
            />
          )}
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4 lg:gap-6">
          {layers.map((l, i) => (
            <Reveal as="article" key={l.step} delay={i * 0.1}>
              <div
                className="group relative flex h-full flex-col overflow-hidden rounded-xl border border-hairline bg-surface/70 p-6 transition-colors duration-300 hover:border-hairline-strong sm:p-7"
              >
                {/* One restrained system accent keeps the three stages cohesive. */}
                <div
                  aria-hidden="true"
                  className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan/45 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                />

                <div className="mb-6 flex items-center gap-3">
                  <div
                    className="grid h-11 w-11 place-items-center rounded-lg border border-hairline-strong bg-surface-2 text-cyan"
                  >
                    {l.icon}
                  </div>
                  <div>
                    <p className="font-mono text-[11px] tracking-[0.18em] text-ink-dim">
                      {l.kicker}
                    </p>
                    <p className="font-mono text-[10px] text-ink-faint">STAGE {l.step}</p>
                  </div>
                </div>

                <h3 className="text-lg font-medium leading-snug tracking-tight text-ink">
                  {l.title}
                </h3>
                <p className="mt-3 text-[14px] leading-relaxed text-ink-dim">{l.body}</p>

                <div className="mt-6 border-t border-hairline pt-5">
                  <p className="mb-3 font-mono text-[10px] tracking-[0.14em] text-ink-faint">
                    EXAMPLE EVIDENCE
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {l.chips.map((label) => (
                      <Chip key={label}>
                        {label}
                      </Chip>
                    ))}
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.32}>
          <div className="mt-8 flex items-center gap-4 rounded-xl border border-hairline-strong bg-surface-2/50 px-6 py-5">
            <LockIcon />
            <p className="text-[15px] font-medium leading-snug text-ink sm:text-base">
              AI can add risk evidence. It can never override a hard safety policy.
            </p>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}

function KeyIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="8.5" cy="12" r="4" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M12.5 12H21m-3 0v3.5M15.5 12v2.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 8.5A3.5 3.5 0 0 1 10.5 6.7M20 8.5a3.5 3.5 0 0 0-6.5-1.8M4 8.5v5A3.5 3.5 0 0 0 7.5 17M20 8.5v5a3.5 3.5 0 0 1-3.5 3.5M12 5.5v13M8 20h8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M8.6 3h6.8L21 8.6v6.8L15.4 21H8.6L3 15.4V8.6L8.6 3Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M9 9h6v6H9z" fill="currentColor" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      className="shrink-0 text-cyan"
      aria-hidden="true"
    >
      <rect x="4" y="10" width="16" height="11" rx="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 10V7.5a4 4 0 1 1 8 0V10" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="15.5" r="1.5" fill="currentColor" />
    </svg>
  );
}
