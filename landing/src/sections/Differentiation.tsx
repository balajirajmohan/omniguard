import { Reveal } from '../components/ui/Reveal';
import { Section, SectionHeading } from '../components/ui/Primitives';

type Support = 'yes' | 'partial' | 'no';

const columns = [
  'Traditional IAM',
  'Generic policy engine',
  'Robot endpoint protection',
  'OmniGuard',
] as const;

const rows: { capability: string; values: [Support, Support, Support, Support] }[] = [
  { capability: 'Validates identity', values: ['yes', 'partial', 'no', 'yes'] },
  { capability: 'Understands destination and path', values: ['no', 'partial', 'partial', 'yes'] },
  { capability: 'Uses live robot/world state', values: ['no', 'no', 'partial', 'yes'] },
  { capability: 'Detects deviations from a versioned behavioral baseline', values: ['no', 'no', 'partial', 'yes'] },
  { capability: 'Simulates controls in a digital twin', values: ['no', 'no', 'no', 'yes'] },
  { capability: 'Revokes and quarantines identities', values: ['partial', 'no', 'no', 'yes'] },
  { capability: 'Triggers robot emergency stop', values: ['no', 'no', 'partial', 'yes'] },
];

export function Differentiation() {
  return (
    <Section id="differentiation">
      <Reveal>
        <SectionHeading
          eyebrow="DIFFERENTIATION"
          title="Security that understands physical consequence."
          body="Each category solves a real problem well. None of them evaluates identity, physical context, and learned behavior as a single decision on the command path."
        />
      </Reveal>

      <Reveal delay={0.12} className="mt-12">
        {/* Table scrolls inside its own container so the page never does. */}
        <div className="overflow-x-auto rounded-xl border border-hairline">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <caption className="sr-only">
              Capability comparison between traditional IAM, generic policy engines, robot endpoint
              protection, and OmniGuard.
            </caption>
            <thead>
              <tr className="border-b border-hairline bg-surface-2/60">
                <th scope="col" className="px-5 py-4 text-[12px] font-medium text-ink-faint">
                  Capability
                </th>
                {columns.map((c) => {
                  const own = c === 'OmniGuard';
                  return (
                    <th
                      key={c}
                      scope="col"
                      className={`px-4 py-4 text-center text-[12.5px] font-medium ${
                        own ? 'bg-cyan/6 text-cyan' : 'text-ink-dim'
                      }`}
                    >
                      {c}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.capability} className="border-b border-hairline/70 last:border-b-0">
                  <th
                    scope="row"
                    className="px-5 py-3.5 text-[13.5px] font-normal leading-snug text-ink"
                  >
                    {r.capability}
                  </th>
                  {r.values.map((v, i) => (
                    <td
                      key={columns[i]}
                      className={`px-4 py-3.5 text-center ${i === 3 ? 'bg-cyan/[0.04]' : ''}`}
                    >
                      <SupportMark value={v} column={columns[i]} capability={r.capability} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>

      <Reveal delay={0.18}>
        <p className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[10.5px] text-ink-faint">
          <span className="flex items-center gap-1.5">
            <CheckMark /> supported
          </span>
          <span className="flex items-center gap-1.5">
            <PartialMark /> partial / vendor-dependent
          </span>
          <span className="flex items-center gap-1.5">
            <NoMark /> not addressed
          </span>
        </p>
      </Reveal>
    </Section>
  );
}

function SupportMark({
  value,
  column,
  capability,
}: {
  value: Support;
  column: string;
  capability: string;
}) {
  const text =
    value === 'yes' ? 'Supported' : value === 'partial' ? 'Partial support' : 'Not addressed';

  return (
    <span className="inline-flex" title={`${column}: ${text}. ${capability}`}>
      <span className="sr-only">{text}</span>
      {value === 'yes' ? <CheckMark /> : value === 'partial' ? <PartialMark /> : <NoMark />}
    </span>
  );
}

function CheckMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3.5 8.4 6.5 11.4l6-7"
        stroke="var(--color-allow)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PartialMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="5.5" stroke="var(--color-warn)" strokeWidth="1.5" opacity="0.7" />
      <path d="M8 2.5a5.5 5.5 0 0 1 0 11V2.5Z" fill="var(--color-warn)" opacity="0.75" />
    </svg>
  );
}

function NoMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M4.5 8h7"
        stroke="var(--color-ink-faint)"
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.6"
      />
    </svg>
  );
}
