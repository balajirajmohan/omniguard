import { useCallback, useMemo, useState } from 'react';
import { PlugZap, Radar, ShieldAlert } from 'lucide-react';
import ControlPanel from './components/ControlPanel.jsx';
import DecisionCard from './components/DecisionCard.jsx';
import InvestigatePanel from './components/InvestigatePanel.jsx';
import ScenarioPanel from './components/ScenarioPanel.jsx';
import SettingsSheet from './components/SettingsSheet.jsx';
import TelemetryRail from './components/TelemetryRail.jsx';
import TopBar from './components/TopBar.jsx';
import WarehouseMap from './components/WarehouseMap.jsx';
import { loadConfig, saveConfig } from './lib/omniguard.js';
import { useController } from './lib/useController.js';

export default function App() {
  const [cfg, setCfg] = useState(loadConfig);
  const [showSettings, setShowSettings] = useState(false);
  const [scenarioResult, setScenarioResult] = useState(null);
  const ctl = useController(cfg);

  /* A scenario run returns its own event synchronously; the poll catches up a
   * beat later. Prefer whichever is newer so the card never flickers backwards. */
  const latestEvent = useMemo(() => {
    const polled = ctl.events[0];
    if (!scenarioResult) return polled;
    if (!polled) return scenarioResult;
    return new Date(polled.timestamp) >= new Date(scenarioResult.timestamp) ? polled : scenarioResult;
  }, [ctl.events, scenarioResult]);

  const onSave = useCallback((next) => {
    setCfg(next);
    saveConfig(next);
    setShowSettings(false);
  }, []);

  const stickHandler = (id) => (next) => ctl.setStick(id, next);
  const revoked = ctl.status.credential_status === 'REVOKED';

  return (
    <div className="mx-auto min-h-screen max-w-[1560px] px-4 py-4 sm:px-5">
      <TopBar
        status={ctl.status}
        pad={ctl.padLabel}
        resetting={ctl.resetting}
        settingsOpen={showSettings}
        health={ctl.health}
        gatewayReady={ctl.gatewayReady}
        onReset={() => { setScenarioResult(null); ctl.reset(); }}
        onToggleSettings={() => setShowSettings((v) => !v)}
      />

      {showSettings && (
        <SettingsSheet cfg={cfg} onSave={onSave} onClose={() => setShowSettings(false)} />
      )}

      {ctl.gatewayReady === false && (
        <div role="status"
          className="a-rise mb-3 flex items-start gap-3 rounded-2xl border border-warn/50 bg-warn/10 px-4 py-3">
          <PlugZap size={17} className="mt-0.5 shrink-0 text-warn" aria-hidden="true" />
          <p className="text-[13px] leading-relaxed text-dim">
            <b className="text-warn">Teleop gateway not deployed.</b>{' '}
            <span className="font-mono text-[12px]">/api/teleop/config</span> is not answering on{' '}
            <span className="font-mono text-[12px]">{cfg.api}</span>, so the joysticks have nothing
            to authorize against. Scenarios, telemetry and investigation still work. Zone geometry
            below is the contract default, not server-authoritative.
          </p>
        </div>
      )}

      {revoked && (
        <div role="alert"
          className="a-rise mb-3 flex items-start gap-3 rounded-2xl border border-bad/50 bg-bad/10 px-4 py-3">
          <ShieldAlert size={17} className="mt-0.5 shrink-0 text-bad" aria-hidden="true" />
          <p className="text-[13px] leading-relaxed text-dim">
            <b className="text-bad">Credential revoked.</b>{' '}
            The rogue controller burned the shared fleet credential, so the legitimate operator is
            locked out too. That is the blast radius of a shared credential — press{' '}
            <b className="text-txt">Reset demo</b> to rotate it.
          </p>
        </div>
      )}

      {/* Map is the hero; telemetry sits beside it rather than under the fold. */}
      <section className="mb-3 grid gap-3 xl:grid-cols-[minmax(0,2.4fr)_minmax(260px,1fr)]">
        <div className="card p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-[15px]">
              <Radar size={15} className="text-info" aria-hidden="true" />Warehouse floor
            </h2>
            <span className="font-mono text-[11px] text-faint">
              {ctl.world.setpoints.length > 0 ? 'tracking setpoint' : 'holding position'}
              {ctl.status.bridge?.speed != null && ` · ${ctl.status.bridge.speed} m/s`}
            </span>
          </div>
          <WarehouseMap
            zones={ctl.teleopConfig.zones}
            robot={ctl.world.robot}
            target={ctl.world.target}
            trail={ctl.world.trail}
            setpoints={ctl.world.setpoints}
          />
        </div>

        <TelemetryRail status={ctl.status} robot={ctl.world.robot} />
      </section>

      <section className="mb-3 grid gap-3 xl:grid-cols-3">
        <ScenarioPanel cfg={cfg} onResult={setScenarioResult} />
        <DecisionCard event={latestEvent} timeline={ctl.timeline} />
        <InvestigatePanel cfg={cfg} />
      </section>

      <main className="a-stagger grid gap-3 lg:grid-cols-2">
        {['legit', 'rogue'].map((id) => (
          <ControlPanel
            key={id}
            panel={id}
            state={ctl.view[id]}
            onStick={stickHandler(id)}
            external={ctl.external[id]}
            options={ctl.options}
            setOptions={ctl.setOptions}
          />
        ))}
      </main>

      <footer className="mt-3 flex flex-wrap justify-between gap-3 text-[11px] text-faint">
        <span>Left stick drives the operator · right stick drives the attacker · arrows or WASD when focused</span>
        <span>
          Browser → OmniGuard {cfg.api} → secured bridge → Isaac. The browser never contacts the
          bridge and never holds its token.
        </span>
      </footer>
    </div>
  );
}
