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

const traceLines: { text: string; tone: string }[] = [
  { text: '> replay identity=fleet-agent-01 device=rogue-laptop', tone: 'text-ink-dim' },
  { text: '  jwt.verify            OK', tone: 'text-allow' },
  { text: '  device.binding        FAIL  (controller-01 ≠ rogue-laptop)', tone: 'text-deny' },
  { text: '  zone.resolve(dest)    HUMAN_ZONE', tone: 'text-warn' },
  { text: '  zone.permitted        FAIL', tone: 'text-deny' },
  { text: '  speed.limit(1.2)      FAIL  (requested 1.80 m/s)', tone: 'text-deny' },
  { text: '  path.intersect        HUMAN_ZONE @ 4.2 m', tone: 'text-deny' },
  { text: '  behavior.score        0.91  CRITICAL', tone: 'text-deny' },
  { text: '> decision              DENY', tone: 'text-deny' },
  { text: '> contain               revoke • quarantine • estop', tone: 'text-deny' },
  { text: '> sim.result            robot halted 1.6 m before boundary', tone: 'text-cyan' },
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
        <Reveal>
          <SectionHeading
            eyebrow="NVIDIA OMNIVERSE + ISAAC SIM"
            title="Prove the policy before it reaches production."
            body="Replay compromised identities, unsafe paths, anomalous behavior, and emergency-stop actions in a photorealistic digital twin. Security and robotics teams can validate the cyber decision and its physical consequence together."
          />
        </Reveal>

        {/* Split screen: policy trace ⟷ simulated physical outcome */}
        <Reveal delay={0.12} className="mt-12">
          <div className="grid grid-cols-1 overflow-hidden rounded-2xl border border-hairline-strong bg-surface/70 lg:grid-cols-2">
            {/* Left: attack command + policy trace */}
            <div className="border-b border-hairline lg:border-b-0 lg:border-r">
              <PanelHeader label="ATTACK COMMAND / POLICY TRACE" tone="text-deny" />
              <div className="p-4 sm:p-5">
                <pre className="overflow-x-auto font-mono text-[11px] leading-[1.75] sm:text-[11.5px]">
                  {traceLines.map((l) => (
                    <div key={l.text} className={l.tone}>
                      {l.text}
                    </div>
                  ))}
                </pre>
              </div>
            </div>

            {/* Right: simulated physical outcome */}
            <div>
              <PanelHeader label="ISAAC SIM / PHYSICAL OUTCOME" tone="text-cyan" />
              <div className="p-4 sm:p-5">
                <SimStopScene />
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.2}>
          <ul className="mt-10 grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
            {bullets.map((b) => (
              <li key={b} className="flex items-start gap-3">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  className="mt-0.5 shrink-0 text-cyan"
                  aria-hidden="true"
                >
                  <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.2" opacity="0.45" />
                  <path
                    d="M4.8 8.2 7 10.4l4.2-4.6"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <span className="text-[14.5px] leading-relaxed text-ink-dim">{b}</span>
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={0.26}>
          <p className="mt-8 font-mono text-[10.5px] leading-relaxed text-ink-faint">
            NVIDIA, Omniverse, and Isaac Sim are referenced as integration targets. Names used
            textually; no affiliation or endorsement is implied.
          </p>
        </Reveal>
      </div>
    </Section>
  );
}

function PanelHeader({ label, tone }: { label: string; tone: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-hairline bg-surface-2/60 px-4 py-2.5 sm:px-5">
      <span className={`font-mono text-[10px] tracking-[0.16em] ${tone}`}>{label}</span>
    </div>
  );
}

/** Simulated robot halting short of the human-zone boundary. */
function SimStopScene() {
  const reduced = useReducedMotion();
  const robot = box(3.1, 4.9, 3.75, 5.55, 16);
  const [hx, hy] = iso(6.4, 6.3, 6);

  return (
    <div className="relative aspect-[4/3] w-full">
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

      <div className="absolute left-3 top-3">
        <Chip tone="deny">HALTED 1.6 m BEFORE BOUNDARY</Chip>
      </div>
      <div className="absolute bottom-3 left-3 flex flex-wrap gap-1.5">
        <Chip tone="cyan">sim tick 4182</Chip>
        <Chip>replay #7</Chip>
      </div>
    </div>
  );
}
