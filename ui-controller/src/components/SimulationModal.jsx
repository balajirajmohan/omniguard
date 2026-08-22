import {useEffect} from "react";
import {
  Bot,
  Hand,
  Orbit,
  Play,
  Route,
  Square,
  TimerReset,
  X,
} from "lucide-react";

const STATUS = {
  running: {
    label: "AUTONOMOUS ROUTE ACTIVE",
    tone: "border-ok/45 bg-ok/10 text-ok",
  },
  override: {
    label: "MANUAL OVERRIDE",
    tone: "border-warn/45 bg-warn/10 text-warn",
  },
  resuming: {
    label: "RESUMING AFTER OVERRIDE",
    tone: "border-info/45 bg-info/10 text-info",
  },
  stopped: {label: "LIVE CONTROL", tone: "border-line bg-sunken text-dim"},
};

export default function SimulationModal({
  simulation,
  onStart,
  onStop,
  onClose,
  disabled,
}) {
  const active = simulation.enabled;
  const status = STATUS[simulation.phase] ?? STATUS.stopped;
  const shuttleActive = active && simulation.scenario === "zone-shuttle";
  const patrolActive = active && simulation.scenario === "zone-a-perimeter";

  useEffect(() => {
    const closeOnEscape = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-void/80 p-4 backdrop-blur-sm"
      role="presentation"
      onPointerDown={(event) =>
        event.target === event.currentTarget && onClose()
      }>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="simulation-title"
        className="card a-rise w-full max-w-[620px] overflow-hidden">
        <div className="flex items-start justify-between gap-4 border-b border-line p-5">
          <div className="flex items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-xl border border-info/30 bg-info/10">
              <Bot size={19} className="text-info" aria-hidden="true" />
            </div>
            <div>
              <h2 id="simulation-title" className="text-[16px]">
                Simulation center
              </h2>
              <p className="mt-1 text-[11.5px] leading-relaxed text-faint">
                Run a warehouse duty cycle while OmniGuard keeps every command
                behind the same identity, lease and policy controls as live
                operation.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close simulation center"
            className="cursor-pointer rounded-lg p-1 text-faint transition-colors hover:text-txt">
            <X size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1
                              font-mono text-[10px] font-semibold ${status.tone}`}>
              <span
                className={`size-1.5 rounded-full ${active ? "a-pulse bg-current" : "bg-faint"}`}
              />
              {status.label}
            </span>
            {active && (
              <span className="chip">
                {patrolActive ? "completed laps" : "completed cycles"}{" "}
                {simulation.completedCycles}
              </span>
            )}
          </div>

          <article
            className={`rounded-2xl border p-4 transition-colors
                               ${shuttleActive ? "border-info/40 bg-info/[.06]" : "border-line bg-sunken/55"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <span className="label mb-1.5">Scenario 1</span>
                <h3 className="flex items-center gap-2 text-[14px]">
                  <Route size={15} className="text-info" aria-hidden="true" />
                  Zone shuttle · A ⇄ B
                </h3>
                <p className="mt-2 max-w-[430px] text-[11.5px] leading-relaxed text-dim">
                  Repeatedly travel from Safe Zone A to Safe Zone B and return
                  to A, modelling a routine warehouse replenishment route.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {shuttleActive ? (
                  <button
                    onClick={onStop}
                    className="btn btn-sm border-bad/35 text-bad hover:border-bad/60">
                    <Square size={12} aria-hidden="true" />
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={() => onStart("zone-shuttle")}
                    disabled={disabled || active}
                    className="btn btn-sm btn-primary"
                    title={
                      disabled
                        ? "Waiting for teleop gateway and robot pose"
                        : undefined
                    }>
                    <Play size={12} aria-hidden="true" />
                    Start scenario
                  </button>
                )}
              </div>
            </div>

            {shuttleActive && (
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <div className="rounded-xl border border-line bg-void/35 p-3">
                  <span className="label">Current objective</span>
                  <p className="mt-1.5 font-mono text-[12px] text-txt">
                    {simulation.phase === "override"
                      ? "Operator has control"
                      : simulation.phase === "resuming"
                        ? "Waiting for idle hand-back"
                        : `Proceed to ${simulation.objective}`}
                  </p>
                </div>
                <div className="rounded-xl border border-line bg-void/35 p-3">
                  <span className="label">Control policy</span>
                  <p className="mt-1.5 font-mono text-[12px] text-txt">
                    {simulation.phase === "override" ||
                    simulation.phase === "resuming"
                      ? "Auto-resume after 3 s idle"
                      : "Controller override ready"}
                  </p>
                </div>
              </div>
            )}
          </article>

          <article
            className={`mt-3 rounded-2xl border p-4 transition-colors
                               ${patrolActive ? "border-violet/45 bg-violet/[.06]" : "border-line bg-sunken/55"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <span className="label mb-1.5">Scenario 2</span>
                <h3 className="flex items-center gap-2 text-[14px]">
                  <Orbit size={15} className="text-violet" aria-hidden="true" />
                  Zone A perimeter patrol
                </h3>
                <p className="mt-2 max-w-[430px] text-[11.5px] leading-relaxed text-dim">
                  Circle clockwise around Safe Zone A on a four-corner route,
                  inset from every boundary for warehouse-floor clearance.
                </p>
              </div>
              {patrolActive ? (
                <button
                  onClick={onStop}
                  className="btn btn-sm border-bad/35 text-bad hover:border-bad/60">
                  <Square size={12} aria-hidden="true" />
                  Stop
                </button>
              ) : (
                <button
                  onClick={() => onStart("zone-a-perimeter")}
                  disabled={disabled || active}
                  className="btn btn-sm btn-primary"
                  title={
                    disabled
                      ? "Waiting for teleop gateway and robot pose"
                      : undefined
                  }>
                  <Play size={12} aria-hidden="true" />
                  Start scenario
                </button>
              )}
            </div>

            {patrolActive && (
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <div className="rounded-xl border border-line bg-void/35 p-3">
                  <span className="label">Current objective</span>
                  <p className="mt-1.5 font-mono text-[12px] text-txt">
                    {simulation.phase === "override"
                      ? "Operator has control"
                      : simulation.phase === "resuming"
                        ? "Waiting for idle hand-back"
                        : `Proceed to ${simulation.objective}`}
                  </p>
                </div>
                <div className="rounded-xl border border-line bg-void/35 p-3">
                  <span className="label">Patrol progress</span>
                  <p className="mt-1.5 font-mono text-[12px] text-txt">
                    {simulation.completedCycles} laps ·{" "}
                    {simulation.completedLegs} legs
                  </p>
                </div>
              </div>
            )}
          </article>

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <div className="flex gap-2.5 rounded-xl border border-line bg-sunken/45 p-3">
              <Hand
                size={14}
                className="mt-0.5 shrink-0 text-warn"
                aria-hidden="true"
              />
              <p className="text-[10.5px] leading-relaxed text-faint">
                <b className="text-dim">Human always wins.</b> Move the operator
                stick or use WASD to pause the route and take immediate control.
              </p>
            </div>
            <div className="flex gap-2.5 rounded-xl border border-line bg-sunken/45 p-3">
              <TimerReset
                size={14}
                className="mt-0.5 shrink-0 text-info"
                aria-hidden="true"
              />
              <p className="text-[10.5px] leading-relaxed text-faint">
                <b className="text-dim">Automatic hand-back.</b> Three seconds
                after the operator releases control, the route continues from
                the robot’s reported pose.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
