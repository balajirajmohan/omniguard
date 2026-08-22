import { useCallback, useEffect, useMemo, useState } from 'react';
import { Grab, Keyboard, PlugZap, Radar, ShieldAlert } from 'lucide-react';
import DecisionCard from './components/DecisionCard.jsx';
import DualSense from './components/DualSense.jsx';
import InvestigatePanel from './components/InvestigatePanel.jsx';
import LogsView from './components/LogsView.jsx';
import PlaneCard from './components/PlaneCard.jsx';
import ScenarioPanel from './components/ScenarioPanel.jsx';
import SettingsSheet from './components/SettingsSheet.jsx';
import TopBar from './components/TopBar.jsx';
import WarehouseMap from './components/WarehouseMap.jsx';
import {
  DEMO_CREDENTIAL, DEMO_OPERATOR_TOKEN, loadConfig, saveConfig,
} from './lib/omniguard.js';
import { useController } from './lib/useController.js';
import { useKeyboardControl } from './lib/useKeyboardControl.js';
import { useSessionLog } from './lib/useSessionLog.js';

export default function App() {
  const [cfg, setCfg] = useState(loadConfig);
  const [showSettings, setShowSettings] = useState(false);
  const [view, setView] = useState('console');
  const [scenarioResult, setScenarioResult] = useState(null);

  const ctl = useController(cfg);
  const logs = useSessionLog();

  /* Window-level, so nothing has to be clicked before the keys work:
   * WASD drives the operator, arrow keys drive the hacker. */
  const keys = useKeyboardControl(ctl.setStick, { actions: ctl.aux });

  useEffect(() => { logs.record(ctl.events); }, [ctl.events, logs]);

  const onSave = useCallback((next) => {
    /* Secrets stay in React memory only — never rely on settings draft/localStorage. */
    const secured = {
      ...next,
      credential: DEMO_CREDENTIAL,
      operatorToken: DEMO_OPERATOR_TOKEN,
    };
    setCfg(secured);
    saveConfig(secured);
    setShowSettings(false);
  }, []);

  /* Archive before the backend wipes its state, or the run just demonstrated
   * would vanish along with it. */
  const handleReset = useCallback(async () => {
    logs.archive({ label: 'reset' });
    setScenarioResult(null);
    await ctl.reset();
  }, [ctl, logs]);

  const latestEvent = useMemo(() => {
    const polled = ctl.events[0];
    if (!scenarioResult) return polled;
    if (!polled) return scenarioResult;
    return new Date(polled.timestamp) >= new Date(scenarioResult.timestamp) ? polled : scenarioResult;
  }, [ctl.events, scenarioResult]);

  const lamps = { legit: ctl.view.legit.lamp, rogue: ctl.view.rogue.lamp };
  const leases = {
    legit: Boolean(ctl.view.legit.lease?.controlId),
    rogue: Boolean(ctl.view.rogue.lease?.controlId),
  };
  const revoked = ctl.status.credential_status === 'REVOKED';

  /* Isaac only reports arm/gripper after it executes a command, and mock mode
   * never reports them, so the chip states plainly where the value came from. */
  const manip = ctl.world.manipulator;
  const manipulatorChip = manip
    ? [manip.arm?.preset ?? (manip.arm ? 'joints' : null), manip.gripper?.action]
        .filter(Boolean).join(' \u00b7 ')
    : 'arm idle';
  const manipulatorTitle = manip
    ? (manip.arm?.source === 'confirmed' || manip.gripper?.source === 'confirmed'
      ? 'Confirmed by isaac_bridge_state'
      : 'Accepted by the backend, not yet confirmed by Isaac')
    : 'No arm or gripper command sent yet';

  return (
    <div className="mx-auto flex min-h-dvh max-w-[1680px] flex-col gap-3 p-3 xl:h-dvh xl:overflow-hidden">
      <TopBar
        status={ctl.status} health={ctl.health} gatewayReady={ctl.gatewayReady}
        view={view} onView={setView} pad={ctl.padLabel} resetting={ctl.resetting}
        settingsOpen={showSettings} onReset={handleReset}
        onToggleSettings={() => setShowSettings((v) => !v)}
      />

      {showSettings && (
        <SettingsSheet cfg={cfg} onSave={onSave} onClose={() => setShowSettings(false)} />
      )}

      {ctl.gatewayReady === false && view === 'console' && (
        <div role="status" className="a-rise flex shrink-0 items-start gap-2.5 rounded-xl
                                      border border-warn/45 bg-warn/10 px-3 py-2">
          <PlugZap size={14} className="mt-px shrink-0 text-warn" aria-hidden="true" />
          <p className="text-[11.5px] leading-relaxed text-dim">
            <b className="text-warn">Teleop gateway not deployed.</b>{' '}
            <span className="font-mono">/api/teleop/config</span> is not answering on{' '}
            <span className="font-mono">{cfg.api}</span>. Scenarios, telemetry and investigation
            still work; zone geometry below is the contract default.
          </p>
        </div>
      )}

      {revoked && (
        <div role="alert" className="a-rise flex shrink-0 items-start gap-2.5 rounded-xl
                                     border border-bad/45 bg-bad/10 px-3 py-2">
          <ShieldAlert size={14} className="mt-px shrink-0 text-bad" aria-hidden="true" />
          <p className="text-[11.5px] leading-relaxed text-dim">
            <b className="text-bad">Credential revoked.</b>{' '}
            The hacker burned the shared fleet credential, so the valid operator is locked out too —
            the blast radius of a shared credential. Press <b className="text-txt">Reset demo</b> to
            rotate it.
          </p>
        </div>
      )}

      {view === 'logs' ? (
        <LogsView sessions={logs.sessions} current={logs.current}
          onRemove={logs.removeSession} onClearAll={logs.clearAll} />
      ) : (
        <>
          {/* Hero: map and controller side by side, both above the fold. */}
          <section className="grid min-h-0 flex-1 gap-3 xl:grid-cols-[minmax(0,1.5fr)_minmax(380px,1fr)]">
            <div className="card flex min-h-0 flex-col p-3.5">
              <div className="mb-2 flex shrink-0 flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-1.5 text-[13.5px]">
                  <Radar size={13} className="text-info" aria-hidden="true" />Warehouse floor
                </h2>
                <div className="flex items-center gap-1.5">
                  <span className="chip">{ctl.status.robot_status ?? '—'}</span>
                  <span className="chip">{ctl.status.robot_zone ?? '—'}</span>
                  <span className="chip">
                    {ctl.world.robot
                      ? `${ctl.world.robot.x.toFixed(1)}, ${ctl.world.robot.y.toFixed(1)}`
                      : 'no pose'}
                  </span>
                  {/* Arm/gripper is absent from mock_bridge_state, so say which
                      source the read-out came from instead of implying truth. */}
                  <span className="chip text-violet" title={manipulatorTitle}>
                    <Grab size={9} aria-hidden="true" />
                    {manipulatorChip}
                  </span>
                </div>
              </div>
              <div className="min-h-0 flex-1">
                <WarehouseMap zones={ctl.teleopConfig.zones} robot={ctl.world.robot}
                  target={ctl.world.target} trail={ctl.world.trail} setpoints={ctl.world.setpoints}
                  manipulator={ctl.world.manipulator} />
              </div>
            </div>

            <div className="flex min-h-0 flex-col gap-3">
              <div className="card flex min-h-0 flex-col p-3.5">
                <div className="mb-1 flex shrink-0 items-center justify-between gap-2">
                  <h2 className="text-[13.5px]">Control surface</h2>
                  <span className="chip">
                    <Keyboard size={9} aria-hidden="true" />
                    <span className={keys.legit ? 'text-ok' : ''}>WASD</span>
                    <span className="text-faint">/</span>
                    <span className={keys.rogue ? 'text-bad' : ''}>arrows</span>
                    <span className="text-faint">· d-pad arm · L1/L2 · R1/R2 grip</span>
                  </span>
                </div>
                <div className="min-h-0 flex-1">
                  <DualSense
                    stickRef={ctl.stickRef} onStick={ctl.setStick} lamps={lamps} leases={leases}
                    driving={keys}
                    onArmPreset={ctl.sendArmPreset} onGripper={ctl.sendGripper}
                    onEmergencyStop={ctl.emergencyStop}
                  />
                </div>
              </div>

              <div className="grid shrink-0 gap-2 sm:grid-cols-2">
                <PlaneCard panel="legit" state={ctl.view.legit} />
                <PlaneCard panel="rogue" state={ctl.view.rogue} />
              </div>
            </div>
          </section>

          {/* Secondary rail, still on screen without scrolling on a laptop. */}
          <section className="a-stagger grid shrink-0 gap-3 xl:h-[228px]
                              xl:grid-cols-[260px_minmax(0,1fr)_280px]">
            <ScenarioPanel cfg={cfg} onResult={setScenarioResult} />
            <DecisionCard event={latestEvent} timeline={ctl.timeline} />
            <InvestigatePanel cfg={cfg} />
          </section>
        </>
      )}
    </div>
  );
}
