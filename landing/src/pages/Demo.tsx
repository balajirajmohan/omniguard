import { useState } from 'react';
import { Link } from 'react-router-dom';
import { LogoMark, Wordmark } from '../components/Logo';
import { Button } from '../components/ui/Button';
import { Chip, Dot, type Tone } from '../components/ui/Primitives';
import { DecisionTrace } from '../components/decision/DecisionTrace';
import { FieldTable } from '../components/decision/FieldTable';
import { RiskMeter } from '../components/decision/RiskMeter';
import { Verdict } from '../components/decision/Verdict';
import { useScenarioRun } from '../components/decision/useScenarioRun';
import { TwinMap } from '../components/scene/TwinMap';
import {
  consoleNav,
  identities,
  incidents,
  policies,
  robots,
  scenarioById,
  scenarios,
  systemStatus,
  POLICY_VERSION,
  type ConsoleNavItem,
  type Outcome,
  type ScenarioId,
} from '../data/demoData';
import { PREVIEW_LABEL, isLiveBackend } from '../config/endpoints';

const DEFAULT_SCENARIO: ScenarioId = 'stolen';

const outcomeTone: Record<Outcome, Tone> = {
  ALLOW: 'allow',
  ALLOW_CONSTRAINED: 'warn',
  DENY: 'deny',
  ESTOP: 'deny',
};

export default function Demo() {
  const [view, setView] = useState<ConsoleNavItem>('Overview');
  const [selected, setSelected] = useState<ScenarioId>(DEFAULT_SCENARIO);
  const [runKey, setRunKey] = useState(0);
  const scenario = scenarioById(selected);
  const { revealed, settled, complete } = useScenarioRun(scenario, runKey);

  const reset = () => {
    setSelected(DEFAULT_SCENARIO);
    setView('Overview');
    setRunKey((k) => k + 1);
  };

  return (
    <div className="flex min-h-screen flex-col bg-graphite">
      {/* ---------------- Top status bar ---------------- */}
      <header className="sticky top-0 z-40 border-b border-hairline bg-graphite/95 backdrop-blur-xl">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5" aria-label="OmniGuard home">
            <LogoMark size={22} />
            <Wordmark className="!text-[15px]" />
          </Link>
          <span className="hidden font-mono text-[10px] tracking-[0.16em] text-ink-faint md:inline">
            OPERATIONS CONSOLE
          </span>

          <ul className="order-3 flex w-full flex-wrap items-center gap-x-4 gap-y-1.5 lg:order-none lg:ml-auto lg:w-auto">
            {systemStatus.map((s) => (
              <li key={s.label} className="flex items-center gap-1.5">
                <Dot tone={s.tone} pulse={isLiveBackend} />
                <span className="font-mono text-[10.5px] text-ink-dim">
                  {s.label} <span className="text-ink">{s.value}</span>
                </span>
              </li>
            ))}
          </ul>

          <Button
            variant="secondary"
            size="sm"
            onClick={reset}
            className="ml-auto lg:ml-4"
            aria-label="Reset the demo to its initial state"
          >
            Reset Demo
          </Button>
        </div>
      </header>

      <div className="flex flex-1 flex-col lg:flex-row">
        {/* ---------------- Left navigation ---------------- */}
        <nav
          aria-label="Console sections"
          className="shrink-0 border-b border-hairline bg-surface/40 lg:w-[212px] lg:border-b-0 lg:border-r"
        >
          <ul className="flex gap-1 overflow-x-auto p-2 lg:flex-col lg:gap-0.5 lg:p-3">
            {consoleNav.map((item) => {
              const active = item === view;
              return (
                <li key={item} className="shrink-0">
                  <button
                    type="button"
                    onClick={() => setView(item)}
                    aria-current={active ? 'page' : undefined}
                    className={`w-full cursor-pointer whitespace-nowrap rounded-md px-3 py-2 text-left text-[13px] transition-colors duration-200 lg:w-full ${
                      active
                        ? 'bg-cyan/10 text-cyan-bright'
                        : 'text-ink-dim hover:bg-surface-2 hover:text-ink'
                    }`}
                  >
                    {item}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* ---------------- Main workspace ---------------- */}
        <main className="min-w-0 flex-1 p-4 sm:p-6">
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-ink">{view}</h1>
            <Chip tone={isLiveBackend ? 'allow' : 'cyan'}>{PREVIEW_LABEL}</Chip>
            <span className="ml-auto font-mono text-[10.5px] text-ink-faint">
              policy {POLICY_VERSION}
            </span>
          </div>

          {view === 'Overview' || view === 'Live Decisions' ? (
            <OverviewView
              key={`${runKey}-${selected}`}
              selected={selected}
              onSelect={setSelected}
              scenario={scenario}
              revealed={revealed}
              settled={settled}
              complete={complete}
              compact={view === 'Live Decisions'}
            />
          ) : view === 'Incidents' ? (
            <IncidentsView />
          ) : view === 'Identities' ? (
            <TableCard
              columns={['Identity', 'Bound device', 'Grants', 'State']}
              rows={identities.map((i) => [
                i.id,
                i.device,
                String(i.grants),
                i.state,
              ])}
              stateTone={(v) =>
                v === 'ACTIVE' ? 'allow' : v === 'QUARANTINED' ? 'deny' : 'warn'
              }
            />
          ) : view === 'Robots' ? (
            <TableCard
              columns={['Robot', 'Model', 'Zone', 'Speed', 'State']}
              rows={robots.map((r) => [r.id, r.model, r.zone, r.speed, r.state])}
              stateTone={(v) => (v === 'ACTIVE' ? 'allow' : v === 'E-STOP' ? 'deny' : 'neutral')}
            />
          ) : view === 'Policies' ? (
            <TableCard
              columns={['Policy ID', 'Name', 'Mode', 'Hits (24h)']}
              rows={policies.map((p) => [p.id, p.name, p.mode, String(p.hits)])}
              stateTone={(v) => (v === 'ENFORCE' ? 'allow' : v === 'OBSERVE' ? 'warn' : 'neutral')}
            />
          ) : (
            <TwinView outcome={scenario.outcome} />
          )}
        </main>
      </div>

      <footer className="border-t border-hairline px-4 py-4 sm:px-6">
        <p className="font-mono text-[10.5px] leading-relaxed text-ink-faint">
          {isLiveBackend
            ? 'Connected to the OmniGuard decision API.'
            : 'Local demo data. See src/data/demoData.ts.'}
        </p>
      </footer>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function OverviewView({
  selected,
  onSelect,
  scenario,
  revealed,
  settled,
  complete,
  compact,
}: {
  selected: ScenarioId;
  onSelect: (id: ScenarioId) => void;
  scenario: ReturnType<typeof scenarioById>;
  revealed: number;
  settled: boolean;
  complete: boolean;
  compact: boolean;
}) {
  return (
    <div className="space-y-5">
      {/* Scenario launcher */}
      <div
        role="radiogroup"
        aria-label="Demo scenario"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
      >
        {scenarios.map((s) => {
          const active = s.id === selected;
          const tone = outcomeTone[s.outcome];
          return (
            <button
              key={s.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onSelect(s.id)}
              className={`cursor-pointer rounded-lg border p-4 text-left transition-all duration-200 ${
                active
                  ? 'border-cyan/50 bg-cyan/8'
                  : 'border-hairline bg-surface-2/40 hover:border-hairline-strong hover:bg-surface-2/80'
              }`}
            >
              <span className="flex items-center gap-2">
                <Dot tone={tone} />
                <span
                  className={`text-[14px] font-medium ${active ? 'text-ink' : 'text-ink-dim'}`}
                >
                  {s.name}
                </span>
              </span>
              <span className="mt-2 block font-mono text-[10.5px] leading-relaxed text-ink-faint">
                {s.command}
              </span>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        {/* Map + command */}
        <div className="space-y-5">
          {!compact && (
            <Card title="WAREHOUSE TWIN / SECTOR_04">
              <TwinMap outcome={scenario.outcome} />
            </Card>
          )}

          <Card title="CURRENT COMMAND">
            <p className="mb-4 break-words font-mono text-[13px] text-cyan-bright">
              {scenario.command}
            </p>
            <FieldTable fields={scenario.fields} />
          </Card>

          <Card title="AI ANOMALY SCORE">
            <RiskMeter value={scenario.aiRisk} active={settled} />
            <p className="mt-4 font-mono text-[10.5px] leading-relaxed text-ink-faint">
              Behavioral evidence only. A hard safety policy cannot be relaxed by this score.
            </p>
          </Card>
        </div>

        {/* Trace + verdict + incidents */}
        <div className="space-y-5">
          <Card title="POLICY EVALUATION TRACE">
            <DecisionTrace scenario={scenario} revealed={revealed} />
          </Card>

          <Card title="CONTAINMENT STATUS">
            <Verdict scenario={scenario} active={complete} />
          </Card>

          {!compact && (
            <Card title="INCIDENT TIMELINE">
              <IncidentTimeline limit={4} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function IncidentsView() {
  return (
    <Card title="INCIDENTS / LAST 24 HOURS">
      <IncidentTimeline />
    </Card>
  );
}

function IncidentTimeline({ limit }: { limit?: number }) {
  const rows = limit ? incidents.slice(0, limit) : incidents;

  return (
    <ol className="space-y-0">
      {rows.map((inc, i) => {
        const tone = outcomeTone[inc.outcome];
        return (
          <li key={inc.id} className="relative flex gap-3.5 pb-4 last:pb-0">
            {i < rows.length - 1 && (
              <span
                aria-hidden="true"
                className="absolute left-[5px] top-4 h-[calc(100%-0.5rem)] w-px bg-hairline"
              />
            )}
            <span className="mt-1.5 shrink-0">
              <Dot tone={tone} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2.5">
                <span className="tabnum font-mono text-[11px] text-ink-faint">{inc.time}</span>
                <span className="font-mono text-[11px] text-ink-dim">{inc.id}</span>
                <Chip tone={tone} className="ml-auto">
                  {inc.outcome.replace('_', ' ')}
                </Chip>
              </div>
              <p className="mt-1 text-[13px] leading-snug text-ink">{inc.summary}</p>
              <p className="mt-0.5 font-mono text-[10.5px] text-ink-faint">{inc.identity}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function TwinView({ outcome }: { outcome: Outcome }) {
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <Card title="ISAAC SIM / WAREHOUSE TWIN">
        <TwinMap outcome={outcome} />
      </Card>
      <Card title="SIMULATION SESSION">
        <dl className="divide-y divide-hairline/70 overflow-hidden rounded-lg border border-hairline">
          {[
            ['runtime', 'Isaac Sim 4.2 (mock)'],
            ['scene', 'warehouse_sector_04.usd'],
            ['sim tick', '4182'],
            ['replay', '#7: stolen credential'],
            ['physics dt', '1/240 s'],
            ['evidence', 'sealed • hash chain valid'],
          ].map(([k, v]) => (
            <div key={k} className="flex items-baseline gap-3 px-3.5 py-2.5">
              <dt className="font-mono text-[11px] text-ink-faint">{k}</dt>
              <dd className="ml-auto text-right font-mono text-[11.5px] text-ink">{v}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}

function TableCard({
  columns,
  rows,
  stateTone,
}: {
  columns: string[];
  rows: string[][];
  stateTone: (value: string) => Tone;
}) {
  return (
    <Card title={columns[0].toUpperCase()}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-left">
          <thead>
            <tr className="border-b border-hairline">
              {columns.map((c) => (
                <th
                  key={c}
                  scope="col"
                  className="px-3 py-2.5 font-mono text-[10px] tracking-[0.14em] text-ink-faint"
                >
                  {c.toUpperCase()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row[0]} className="border-b border-hairline/60 last:border-b-0">
                {row.map((cell, i) => {
                  const isState = i === row.length - 1;
                  return (
                    <td key={i} className="px-3 py-3">
                      {isState ? (
                        <Chip tone={stateTone(cell)}>{cell}</Chip>
                      ) : (
                        <span
                          className={`font-mono text-[12px] ${i === 0 ? 'text-ink' : 'text-ink-dim'}`}
                        >
                          {cell}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-xl border border-hairline bg-surface/60">
      <div className="border-b border-hairline bg-surface-2/50 px-4 py-2.5">
        <h2 className="font-mono text-[10px] tracking-[0.16em] text-ink-faint">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}
