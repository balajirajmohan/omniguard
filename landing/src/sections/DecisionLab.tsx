import { useState } from 'react';
import { Reveal } from '../components/ui/Reveal';
import { Section, SectionHeading, Dot } from '../components/ui/Primitives';
import { ArrowRight, ButtonLink } from '../components/ui/Button';
import { ScenarioPicker } from '../components/decision/ScenarioPicker';
import { DecisionTrace } from '../components/decision/DecisionTrace';
import { FieldTable } from '../components/decision/FieldTable';
import { RiskMeter } from '../components/decision/RiskMeter';
import { Verdict } from '../components/decision/Verdict';
import { useScenarioRun } from '../components/decision/useScenarioRun';
import { scenarioById, POLICY_VERSION, type ScenarioId } from '../data/demoData';
import { OPERATIONS_CONSOLE_URL, PREVIEW_LABEL } from '../config/endpoints';

export function DecisionLab() {
  const [selected, setSelected] = useState<ScenarioId>('stolen');
  const scenario = scenarioById(selected);
  const { revealed, settled, complete } = useScenarioRun(scenario);

  return (
    <Section id="decision-lab" className="scroll-mt-24">
      <Reveal>
        <SectionHeading
          eyebrow="INTERACTIVE DECISION LAB"
          title="See OmniGuard decide in real time."
          body="Pick a scenario and watch the same six-stage authorization path run. Deterministic policy and behavioral risk are reported separately, so it is always clear which one produced the outcome."
        />
      </Reveal>

      <Reveal delay={0.12} className="mt-12">
        <div className="overflow-hidden rounded-2xl border border-hairline-strong bg-surface/60">
          {/* Console chrome */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-hairline bg-surface-2/60 px-4 py-3 sm:px-6">
            <div className="flex items-center gap-2">
              <Dot tone="cyan" />
              <span className="font-mono text-[10.5px] tracking-[0.14em] text-ink-dim">
                {PREVIEW_LABEL.toUpperCase()}
              </span>
            </div>
            <span className="ml-auto font-mono text-[10.5px] text-ink-faint">
              policy {POLICY_VERSION}
            </span>
            <span className="hidden font-mono text-[10.5px] text-ink-faint sm:inline">
              engine edge-local
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
            {/* ---- Scenario selector ---- */}
            <div className="border-b border-hairline p-4 sm:p-6 lg:border-b-0 lg:border-r">
              <p className="mb-4 font-mono text-[10px] tracking-[0.16em] text-ink-faint">
                SCENARIO
              </p>
              <ScenarioPicker selected={selected} onSelect={setSelected} />

              <div className="mt-6 rounded-lg border border-hairline bg-surface-2/40 p-3.5">
                <p className="font-mono text-[10px] tracking-[0.14em] text-ink-faint">COMMAND</p>
                <p className="mt-1.5 break-words font-mono text-[12px] text-cyan-bright">
                  {scenario.command}
                </p>
              </div>
            </div>

            {/* ---- Decision output ---- */}
            <div className="p-4 sm:p-6">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div>
                  <p className="mb-3 font-mono text-[10px] tracking-[0.16em] text-ink-faint">
                    COMMAND CONTEXT
                  </p>
                  <FieldTable fields={scenario.fields} />

                  <div className="mt-6">
                    <RiskMeter value={scenario.aiRisk} active={settled} />
                  </div>
                </div>

                <div>
                  <p className="mb-3 font-mono text-[10px] tracking-[0.16em] text-ink-faint">
                    DECISION TRACE
                  </p>
                  <DecisionTrace scenario={scenario} revealed={revealed} />
                </div>
              </div>

              <div className="mt-6">
                <Verdict scenario={scenario} active={complete} />
              </div>
            </div>
          </div>

          {/* Console footer */}
          <div className="flex flex-wrap items-center gap-4 border-t border-hairline bg-surface-2/40 px-4 py-4 sm:px-6">
            <ButtonLink href={OPERATIONS_CONSOLE_URL} size="sm" className="ml-auto">
              Open Live Operations Console
              <ArrowRight />
            </ButtonLink>
          </div>
        </div>
      </Reveal>
    </Section>
  );
}
