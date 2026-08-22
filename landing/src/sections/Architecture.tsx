import { Reveal } from '../components/ui/Reveal';
import { Section, SectionHeading } from '../components/ui/Primitives';
import { useReducedMotion } from '../hooks/useMotionPrefs';

const chain = [
  { label: 'AI Agent / Fleet Manager / Operator', kind: 'source' },
  { label: 'OmniGuard Enforcement Gateway', kind: 'gate' },
  { label: 'Identity & Device Verification', kind: 'stage' },
  { label: 'Physical Policy Engine', kind: 'stage' },
  { label: 'Behavioral Anomaly Model', kind: 'stage' },
  { label: 'Decision & Containment Orchestrator', kind: 'stage' },
  { label: 'Robot Adapter', kind: 'stage' },
  { label: 'Real Robot or Isaac Sim Digital Twin', kind: 'sink' },
] as const;

const feedback = [
  'Position and velocity',
  'Force/torque telemetry',
  'Nearby humans and zones',
  'Robot state',
  'Incident outcomes',
];

const deployment = [
  'Runs at the edge or in a customer-controlled environment',
  'Vendor-neutral robot adapter layer',
  'Local policy decisions without requiring an LLM call',
  'Tamper-evident decision evidence',
  'Integrates with existing IAM, SIEM, and fleet systems',
];

const kindStyle = {
  source: 'border-hairline-strong bg-surface-2 text-ink',
  gate: 'border-cyan/50 bg-cyan/8 text-cyan-bright',
  stage: 'border-hairline bg-surface-2/60 text-ink-dim',
  sink: 'border-allow/40 bg-allow/6 text-allow',
} as const;

export function Architecture() {
  const reduced = useReducedMotion();

  return (
    <Section id="architecture">
      <Reveal>
        <SectionHeading
          eyebrow="ARCHITECTURE"
          title="Designed for the command path, not bolted onto the dashboard."
          body="OmniGuard sits inline. Every instruction that could move a machine passes through the same enforcement gateway, and every physical consequence flows back as evidence."
        />
      </Reveal>

      <div className="mt-12 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,340px)]">
        {/* ---- Diagram ---- */}
        <Reveal>
          <div className="relative h-full overflow-hidden rounded-2xl border border-hairline-strong bg-surface/60 p-5 sm:p-7">
            <div aria-hidden="true" className="bg-grid-fine absolute inset-0 opacity-40" />

            <ol className="relative space-y-0">
              {chain.map((node, i) => (
                <li key={node.label}>
                  <div
                    className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition-colors duration-300 ${kindStyle[node.kind]}`}
                  >
                    <span className="font-mono text-[10px] tabnum text-ink-faint">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span className="text-[13.5px] font-medium leading-snug">{node.label}</span>
                  </div>

                  {i < chain.length - 1 && (
                    <div className="relative ml-8 h-6 w-px overflow-hidden bg-hairline-strong">
                      {!reduced && (
                        <span
                          className="absolute inset-x-0 h-3 bg-gradient-to-b from-transparent via-cyan to-transparent"
                          style={{
                            animation: `og-flow-v 3.2s linear ${i * 0.22}s infinite`,
                          }}
                        />
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ol>

            {/* Feedback loop */}
            <div className="relative mt-7 rounded-lg border border-dashed border-cyan/30 bg-cyan/[0.03] p-4">
              <p className="mb-3 flex items-center gap-2 font-mono text-[10px] tracking-[0.14em] text-cyan">
                <ReturnIcon />
                FEEDBACK SIGNALS → OMNIGUARD
              </p>
              <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                {feedback.map((f) => (
                  <span key={f} className="font-mono text-[11px] text-ink-dim">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Reveal>

        {/* ---- Deployment model ---- */}
        <Reveal delay={0.12}>
          <div className="h-full rounded-2xl border border-hairline bg-surface-2/40 p-6 sm:p-7">
            <h3 className="text-lg font-medium tracking-tight text-ink">Deployment model</h3>
            <ul className="mt-5 space-y-4">
              {deployment.map((d) => (
                <li key={d} className="flex items-start gap-3">
                  <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-cyan" />
                  <span className="text-[14px] leading-relaxed text-ink-dim">{d}</span>
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}

function ReturnIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d="M12 3v3.5a3 3 0 0 1-3 3H2m0 0 3-3M2 9.5l3 3"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
