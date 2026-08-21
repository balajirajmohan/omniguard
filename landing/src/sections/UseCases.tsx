import type { ReactNode } from 'react';
import { Reveal } from '../components/ui/Reveal';
import { Section, SectionHeading } from '../components/ui/Primitives';

const cases: { title: string; body: string; icon: ReactNode; tag: string }[] = [
  {
    title: 'Warehousing & Logistics',
    body: 'Prevent compromised autonomous mobile robots from entering active human or restricted zones.',
    tag: 'AMR FLEETS',
    icon: <RackIcon />,
  },
  {
    title: 'Manufacturing',
    body: 'Authorize high-impact robotic operations using operator identity, task context, cell state, and safety envelopes.',
    tag: 'ROBOTIC CELLS',
    icon: <ArmIcon />,
  },
  {
    title: 'Healthcare Robotics',
    body: 'Constrain service robots to approved areas and respond to unusual identity or movement behavior.',
    tag: 'SERVICE ROBOTS',
    icon: <PulseIcon />,
  },
  {
    title: 'Critical Infrastructure',
    body: 'Govern autonomous inspection systems where an incorrect physical action can disrupt essential operations.',
    tag: 'INSPECTION',
    icon: <GridIcon />,
  },
];

export function UseCases() {
  return (
    <Section id="use-cases">
      <Reveal>
        <SectionHeading
          eyebrow="USE CASES"
          title="Where an unauthorized action has weight, speed, and consequence."
        />
      </Reveal>

      <div className="mt-12 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {cases.map((c, i) => (
          <Reveal as="article" key={c.title} delay={i * 0.08}>
            <div className="group relative h-full overflow-hidden rounded-xl border border-hairline bg-surface/70 p-6 transition-colors duration-300 hover:border-cyan/40">
              <div
                aria-hidden="true"
                className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan/60 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
              />
              <div className="mb-5 grid h-11 w-11 place-items-center rounded-lg border border-hairline-strong bg-surface-2 text-cyan transition-colors duration-300 group-hover:border-cyan/40">
                {c.icon}
              </div>
              <p className="mb-2 font-mono text-[10px] tracking-[0.16em] text-ink-faint">{c.tag}</p>
              <h3 className="text-[15.5px] font-medium leading-snug tracking-tight text-ink">
                {c.title}
              </h3>
              <p className="mt-2.5 text-[13.5px] leading-relaxed text-ink-dim">{c.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}

function RackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M3 20V6l9-3 9 3v14" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M3 11h18M3 15.5h18M12 3v17" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
    </svg>
  );
}

function ArmIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 21v-3.5h5M6.5 17.5 11 7m0 0 6 2.5M11 7l1.5-3.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="11" cy="7" r="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M17 9.5v3.5h3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function PulseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M2.5 12h4l2.5-6 4 12 2.5-6h6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 2.5 20.5 7v10L12 21.5 3.5 17V7L12 2.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M12 11.5 20.5 7M12 11.5 3.5 7M12 11.5v10" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
    </svg>
  );
}
