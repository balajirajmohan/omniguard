import { Reveal } from '../components/ui/Reveal';
import { Section, SectionHeading, Chip } from '../components/ui/Primitives';
import { useReducedMotion } from '../hooks/useMotionPrefs';
import { iso, quad, box, pt } from '../components/scene/isometric';

const bullets = [
  'Test adversarial command scenarios safely',
  'Validate path and zone controls against a shared world model',
  'Generate synthetic edge cases for behavioral AI',
  'Capture repeatable audit evidence for engineering and governance',
];

const checkpoints = [
  {
    id: '01',
    label: 'Identity accepted',
    detail: 'fleet-agent-01 · JWT signature valid',
    status: 'PASS',
    tone: 'text-allow',
  },
  {
    id: '02',
    label: 'Origin rejected',
    detail: 'controller-01 does not match rogue-laptop',
    status: 'FAIL',
    tone: 'text-deny',
  },
  {
    id: '03',
    label: 'Physical envelope crossed',
    detail: 'RESTRICTED_ZONE at 4.2 m · requested 1.80 m/s',
    status: 'FAIL',
    tone: 'text-deny',
  },
  {
    id: '04',
    label: 'Behavior off profile',
    detail: 'Isolation Forest risk 0.91 · critical',
    status: 'RISK',
    tone: 'text-warn',
  },
  {
    id: '05',
    label: 'Containment confirmed',
    detail: 'credential revoked · identity quarantined · E-STOP',
    status: 'DONE',
    tone: 'text-cyan',
  },
];

export function DigitalTwin() {
  return (
    <Section id="digital-twin" bleed className="overflow-hidden">
      {/* Cinematic full-bleed backdrop. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-void via-graphite to-void" />
        <div className="bg-grid mask-fade-edges absolute inset-0 opacity-50" />
        <div
          className="absolute left-1/2 top-1/2 h-[520px] w-[1100px] -translate-x-1/2 -translate-y-1/2 opacity-40"
          style={{
            background:
              'radial-gradient(ellipse at center, rgba(34,211,238,0.14), rgba(34,211,238,0) 70%)',
          }}
        />
      </div>

      <div className="relative mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        <div className="grid items-end gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <Reveal>
            <SectionHeading
              eyebrow="NVIDIA OMNIVERSE + ISAAC SIM"
              title="A flight recorder for every physical decision."
              body="Replay a compromised command, inspect every security checkpoint, and verify the physical outcome in the same evidence package before the policy reaches production."
            />
          </Reveal>
          <Reveal delay={0.08}>
            <div className="border-l border-cyan/30 pl-5">
              <p className="font-mono text-[10px] tracking-[0.16em] text-ink-faint">
                REPLAY STATUS
              </p>
              <p className="mt-2 text-xl font-medium text-ink">Incident contained</p>
              <p className="mt-1 text-sm leading-relaxed text-ink-dim">
                Robot halted 1.6 m before the protected boundary.
              </p>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.12} className="mt-12">
          <div className="overflow-hidden rounded-2xl border border-hairline-strong bg-surface/75">
            <div className="flex flex-wrap items-center gap-3 border-b border-hairline bg-surface-2/55 px-5 py-4 sm:px-6">
              <span className="font-mono text-[10px] tracking-[0.16em] text-cyan">
                INCIDENT FLIGHT RECORDER
              </span>
              <span className="font-mono text-[10px] text-ink-faint">REPLAY / 007</span>
              <div className="ml-auto flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-allow" />
                <span className="font-mono text-[10px] tracking-[0.12em] text-ink-dim">
                  EVIDENCE SEALED
                </span>
              </div>
            </div>

            <div className="grid lg:grid-cols-[0.82fr_1.18fr]">
              <div className="border-b border-hairline p-5 sm:p-7 lg:border-b-0 lg:border-r">
                <div className="rounded-lg border border-hairline bg-graphite/70 px-4 py-3">
                  <p className="font-mono text-[9px] tracking-[0.14em] text-ink-faint">
                    REPLAYED COMMAND
                  </p>
                  <p className="mt-2 font-mono text-[11px] leading-relaxed text-ink-dim">
                    fleet-agent-01 / rogue-laptop / MOVE RESTRICTED_ZONE / 1.80 m/s
                  </p>
                </div>

                <ol className="relative mt-6 space-y-0 before:absolute before:bottom-5 before:left-[13px] before:top-5 before:w-px before:bg-hairline-strong">
                  {checkpoints.map((checkpoint) => (
                    <li key={checkpoint.id} className="relative grid grid-cols-[28px_1fr_auto] gap-3 py-3.5">
                      <span className="relative z-10 grid h-7 w-7 place-items-center rounded-full border border-hairline-strong bg-surface-2 font-mono text-[9px] text-ink-faint">
                        {checkpoint.id}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[13.5px] font-medium text-ink">{checkpoint.label}</p>
                        <p className="mt-1 font-mono text-[9.5px] leading-relaxed text-ink-faint">
                          {checkpoint.detail}
                        </p>
                      </div>
                      <span className={`pt-0.5 font-mono text-[9px] tracking-[0.12em] ${checkpoint.tone}`}>
                        {checkpoint.status}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="relative min-h-[28rem] p-5 sm:p-7">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-mono text-[9px] tracking-[0.14em] text-ink-faint">
                      PHYSICAL OUTCOME / ISAAC SIM
                    </p>
                    <p className="mt-1.5 text-base font-medium text-ink">Boundary interception</p>
                  </div>
                  <Chip tone="deny">DENIED · 42 ms</Chip>
                </div>
                <div className="mt-3">
                  <SimStopScene />
                </div>
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.2}>
          <ul className="mt-6 grid grid-cols-1 overflow-hidden rounded-xl border border-hairline bg-surface/45 sm:grid-cols-2 lg:grid-cols-4">
            {bullets.map((bullet, index) => (
              <li
                key={bullet}
                className="border-b border-hairline p-5 last:border-b-0 sm:[&:nth-child(odd)]:border-r lg:border-b-0 lg:border-r lg:last:border-r-0"
              >
                <span className="font-mono text-[9px] tracking-[0.14em] text-cyan/70">
                  0{index + 1}
                </span>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-dim">{bullet}</p>
              </li>
            ))}
          </ul>
        </Reveal>

      </div>
    </Section>
  );
}

/** Simulated robot halting short of the human-zone boundary. */
function SimStopScene() {
  const reduced = useReducedMotion();
  const robot = box(3.1, 4.9, 3.75, 5.55, 16);
  const [hx, hy] = iso(6.4, 6.3, 6);

  return (
    <div className="relative aspect-[16/10] w-full">
      <svg viewBox="0 0 460 345" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <linearGradient id="og-sim-floor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#101a26" />
            <stop offset="100%" stopColor="#080d14" />
          </linearGradient>
        </defs>
        <g transform="translate(-100, -120) scale(0.85)">
          <polygon points={quad(0, 0, 8, 8)} fill="url(#og-sim-floor)" />
          <g stroke="#22d3ee" strokeOpacity="0.09" strokeWidth="0.8">
            {Array.from({ length: 9 }, (_, i) => {
              const [a, b] = iso(i, 0);
              const [c, d] = iso(i, 8);
              return <line key={`x${i}`} x1={a} y1={b} x2={c} y2={d} />;
            })}
            {Array.from({ length: 9 }, (_, i) => {
              const [a, b] = iso(0, i);
              const [c, d] = iso(8, i);
              return <line key={`y${i}`} x1={a} y1={b} x2={c} y2={d} />;
            })}
          </g>

          {/* Human zone boundary */}
          <polygon
            points={quad(4.3, 4.3, 7.6, 7.6)}
            fill="#ff5533"
            fillOpacity="0.1"
            stroke="#ff5533"
            strokeOpacity="0.6"
            strokeWidth="1.4"
            strokeDasharray="6 4"
          />

          {/* Travelled path, truncated at the halt point */}
          <path
            d={`M${pt(1.2, 4.6, 3)} L${pt(2.3, 4.7, 3)} L${pt(3.4, 5.2, 3)}`}
            fill="none"
            stroke="#22d3ee"
            strokeOpacity="0.7"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="9 7"
            style={reduced ? undefined : { animation: 'og-dash 4s linear infinite' }}
          />
          {/* Blocked continuation */}
          <path
            d={`M${pt(3.4, 5.2, 3)} L${pt(5.4, 5.9, 3)}`}
            fill="none"
            stroke="#ff5533"
            strokeOpacity="0.35"
            strokeWidth="1.6"
            strokeDasharray="2 6"
          />

          {/* Halted robot */}
          <polygon points={robot.left} fill="#12202c" stroke="#2a3849" strokeWidth="0.8" />
          <polygon points={robot.right} fill="#182a38" stroke="#2a3849" strokeWidth="0.8" />
          <polygon points={robot.top} fill="#3a1a16" stroke="#ff5533" strokeWidth="1.3" />

          {/* Human */}
          <g transform={`translate(${hx - 5}, ${hy - 30})`}>
            <circle cx="5" cy="5" r="4.2" fill="#ff8a6b" />
            <path d="M5 10.5c-3.4 0-5 2.2-5 5.6v6.2h10v-6.2c0-3.4-1.6-5.6-5-5.6Z" fill="#ff8a6b" />
            <path
              d="M2.4 22.3 1 30M7.6 22.3 9 30"
              stroke="#ff8a6b"
              strokeWidth="2.2"
              strokeLinecap="round"
            />
          </g>
        </g>
      </svg>

      <div className="absolute bottom-3 left-3 flex flex-wrap gap-1.5">
        <Chip tone="cyan">HALTED 1.6 m BEFORE BOUNDARY</Chip>
        <Chip>SIM TICK 4182</Chip>
      </div>
    </div>
  );
}
