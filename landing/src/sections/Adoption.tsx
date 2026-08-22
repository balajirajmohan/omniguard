import { Reveal } from '../components/ui/Reveal';
import { Section, SectionHeading } from '../components/ui/Primitives';
import { ArrowRight, ButtonLink } from '../components/ui/Button';
import { OPERATIONS_CONSOLE_URL } from '../config/endpoints';

const steps = [
  {
    n: '01',
    name: 'Observe',
    body: 'Collect baseline telemetry and score commands in shadow mode without blocking operations.',
    tone: 'text-cyan border-cyan/40',
    bar: 'from-cyan/60',
  },
  {
    n: '02',
    name: 'Enforce',
    body: 'Enable hard policies for robot, zone, path, device, and speed controls.',
    tone: 'text-warn border-warn/40',
    bar: 'from-warn/60',
  },
  {
    n: '03',
    name: 'Scale',
    body: 'Add fleet-wide policy packs, digital-twin validation, SIEM integrations, and governance reporting.',
    tone: 'text-allow border-allow/40',
    bar: 'from-allow/60',
  },
];

export function Adoption() {
  return (
    <Section id="adopt">
      <Reveal>
        <SectionHeading
          eyebrow="ADOPTION"
          title="Start with one high-risk workflow. Expand across the fleet."
        />
      </Reveal>

      <div className="mt-12 grid grid-cols-1 gap-5 md:grid-cols-3">
        {steps.map((s, i) => (
          <Reveal key={s.n} delay={i * 0.09}>
            <div className="relative h-full overflow-hidden rounded-xl border border-hairline bg-surface/70 p-6 sm:p-7">
              <div
                aria-hidden="true"
                className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r to-transparent ${s.bar}`}
              />
              <div
                className={`mb-5 inline-grid h-10 w-10 place-items-center rounded-lg border bg-graphite font-mono text-[12px] ${s.tone}`}
              >
                {s.n}
              </div>
              <h3 className="text-lg font-medium tracking-tight text-ink">{s.name}</h3>
              <p className="mt-2.5 text-[14px] leading-relaxed text-ink-dim">{s.body}</p>
            </div>
          </Reveal>
        ))}
      </div>

      <Reveal delay={0.28}>
        <div className="mt-10 rounded-xl border border-hairline-strong bg-surface-2/50 p-6 sm:p-8">
          <p className="max-w-3xl text-[16px] font-medium leading-relaxed text-ink sm:text-[17px]">
            OmniGuard gives security teams control, robotics teams deterministic safety, and
            operations teams evidence without replacing the fleet platform.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <ButtonLink href={OPERATIONS_CONSOLE_URL}>
              Open Live Operations Console
              <ArrowRight />
            </ButtonLink>
            <ButtonLink href="#architecture" variant="secondary">
              View Technical Architecture
            </ButtonLink>
          </div>
        </div>
      </Reveal>
    </Section>
  );
}
