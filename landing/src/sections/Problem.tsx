import { Reveal } from '../components/ui/Reveal';
import { Section, SectionHeading } from '../components/ui/Primitives';

const stages = [
  {
    n: '01',
    title: 'Credential is stolen or replayed',
    body: 'A signed token is lifted from a controller, a CI job, or an agent runtime.',
    tone: 'warn',
  },
  {
    n: '02',
    title: 'Traditional IAM verifies the signature',
    body: 'The token is well-formed and unexpired, so it passes. Nothing is wrong — cryptographically.',
    tone: 'warn',
  },
  {
    n: '03',
    title: 'Unsafe robot command is accepted',
    body: 'A 1.8 m/s move order is issued toward an occupied human zone.',
    tone: 'deny',
  },
  {
    n: '04',
    title: 'A software breach becomes a physical incident',
    body: 'The blast radius is no longer data. It is a moving 400 kg machine.',
    tone: 'deny',
  },
] as const;

const toneRing = {
  warn: 'border-warn/30 text-warn',
  deny: 'border-deny/40 text-deny',
} as const;

export function Problem() {
  return (
    <Section id="problem">
      <Reveal>
        <SectionHeading
          eyebrow="THE GAP"
          title="A valid credential can still produce an unsafe action."
        />
      </Reveal>

      <div className="relative mt-14">
        {/* Connector rail */}
        <div
          aria-hidden="true"
          className="absolute left-6 top-0 hidden h-full w-px bg-gradient-to-b from-warn/40 via-deny/40 to-transparent md:left-0 md:top-6 md:h-px md:w-full md:bg-gradient-to-r"
        />

        <ol className="relative grid grid-cols-1 gap-8 md:grid-cols-4 md:gap-6">
          {stages.map((s, i) => (
            <Reveal as="li" key={s.n} delay={i * 0.08} className="relative pl-16 md:pl-0">
              <div
                className={`absolute left-0 top-0 grid h-12 w-12 place-items-center rounded-full border bg-graphite font-mono text-[12px] md:relative md:mb-5 ${toneRing[s.tone]}`}
              >
                {s.n}
              </div>
              <h3 className="text-[15px] font-medium leading-snug text-ink">{s.title}</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-ink-dim">{s.body}</p>
            </Reveal>
          ))}
        </ol>

        {/* OmniGuard inserted between stages 2 and 3 */}
        <Reveal delay={0.3} className="mt-12">
          <div className="relative overflow-hidden rounded-xl border border-cyan/35 bg-cyan/[0.04] p-6 sm:p-7">
            <div
              aria-hidden="true"
              className="bg-grid-fine absolute inset-0 opacity-60"
            />
            <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
              <div className="flex items-center gap-3">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border border-cyan/40 bg-graphite">
                  <ShieldPathIcon />
                </div>
                <div className="font-mono text-[11px] leading-tight tracking-[0.14em] text-cyan">
                  OMNIGUARD
                  <br />
                  <span className="text-ink-faint">INSERTED AT 02 → 03</span>
                </div>
              </div>
              <div className="h-px w-full bg-cyan/20 sm:h-10 sm:w-px" />
              <p className="text-[15px] font-medium leading-snug text-ink sm:text-base">
                Continuous authorization does not stop at login.
              </p>
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.36}>
          <p className="mt-10 max-w-3xl text-[15px] leading-relaxed text-ink-dim">
            Cloud authorization systems understand users, APIs, and data. Robot controllers
            understand movement. OmniGuard connects both domains by evaluating identity, behavior,
            and the physical world in one decision.
          </p>
        </Reveal>
      </div>
    </Section>
  );
}

function ShieldPathIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 2.5 20.5 7v6.4c0 4.6-3.4 8-8.5 9.6-5.1-1.6-8.5-5-8.5-9.6V7L12 2.5Z"
        stroke="#22d3ee"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M7 15.5c2.4 0 2.6-4.5 5-4.5s2.6 4.5 5 4.5"
        stroke="#67e8f9"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
