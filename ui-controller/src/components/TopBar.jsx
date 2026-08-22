import { Brain, Cpu, Gamepad2, Radio, RotateCcw, ScrollText, Settings, Shield, ShieldAlert, Zap } from 'lucide-react';

function Tab({ active, onClick, icon: Icon, children }) {
  return (
    <button onClick={onClick}
      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2.5 py-1.5
                  text-[11.5px] font-semibold transition-colors
                  ${active ? 'bg-elevated text-txt shadow-[0_1px_0_rgba(255,255,255,.06)_inset]'
                           : 'text-faint hover:text-dim'}`}
      aria-current={active ? 'page' : undefined}>
      <Icon size={12} aria-hidden="true" />{children}
    </button>
  );
}

export default function TopBar({
  status, health, gatewayReady, view, onView, onReset, onToggleSettings,
  pad, resetting, settingsOpen, aiAvailable,
}) {
  const online = status.online !== false && status.robot_status !== 'API DOWN';
  const ai = health?.anomaly;

  return (
    <header className="flex shrink-0 flex-wrap items-center gap-3">
      <div className="flex items-center gap-2.5">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl"
          style={{
            background: 'conic-gradient(from 140deg,#1d4ed8,#059669,#a78bfa,#1d4ed8)',
            boxShadow: '0 0 22px -4px rgba(5,150,105,.7)',
          }}>
          <Zap size={16} className="text-white" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-[17px] leading-none">OmniGuard</h1>
          <p className="mt-1 text-[10.5px] text-faint">Zero-Trust command center</p>
        </div>
      </div>

      <nav className="flex items-center gap-1 rounded-xl border border-line bg-sunken/70 p-1"
        aria-label="Views">
        <Tab active={view === 'console'} onClick={() => onView('console')} icon={Shield}>Console</Tab>
        <Tab active={view === 'incidents'} onClick={() => onView('incidents')} icon={ShieldAlert}>Incidents</Tab>
        <Tab active={view === 'logs'} onClick={() => onView('logs')} icon={ScrollText}>Logs</Tab>
      </nav>

      <div className="flex flex-1 flex-wrap items-center gap-1.5">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1
                          text-[10px] font-semibold
                          ${online ? 'border-ok/45 bg-ok/10 text-ok' : 'border-bad/45 bg-bad/10 text-bad'}`}>
          <span className="relative flex size-1.5">
            {online && <span className="a-ping absolute inset-0 rounded-full bg-ok" />}
            <span className={`relative size-1.5 rounded-full ${online ? 'bg-ok' : 'bg-bad'}`} />
          </span>
          {online ? 'BROKER LIVE' : 'BROKER DOWN'}
        </span>

        <span title="Backend-mediated teleoperation gateway"
          className={`chip ${gatewayReady === true ? 'border-ok/45 text-ok'
            : gatewayReady === false ? 'border-warn/45 text-warn' : ''}`}>
          <Radio size={9} aria-hidden="true" />
          gateway {gatewayReady === true ? 'ready' : gatewayReady === false ? 'not deployed' : '…'}
        </span>

        {/* AI service status */}
        {aiAvailable != null && (
          <span title={aiAvailable ? 'AI incident service available' : 'AI incident service not deployed'}
            className={`chip ${aiAvailable ? 'border-ok/45 text-ok' : 'border-warn/45 text-warn'}`}
            aria-label={aiAvailable ? 'AI service available' : 'AI service not deployed'}>
            <Brain size={9} aria-hidden="true" />
            AI {aiAvailable ? 'available' : 'not deployed'}
          </span>
        )}

        {ai && (
          <span title={`artifact ${ai.artifact_verified ? 'verified' : 'UNVERIFIED'} · ${ai.n_training_samples} samples`}
            className={`chip hidden lg:inline-flex ${ai.degraded ? 'border-warn/45 text-warn' : ''}`}>
            <Cpu size={9} aria-hidden="true" />
            {ai.model_version} · advisory only
          </span>
        )}

        <span className="chip hidden xl:inline-flex">
          <Gamepad2 size={9} aria-hidden="true" />{pad}
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <button onClick={onToggleSettings} aria-expanded={settingsOpen} className="btn btn-sm">
          <Settings size={12} aria-hidden="true" />Settings
        </button>
        <button onClick={onReset} disabled={resetting} className="btn btn-sm btn-primary">
          <RotateCcw size={12} aria-hidden="true" className={resetting ? 'animate-spin' : ''} />
          {resetting ? 'Resetting' : 'Reset demo'}
        </button>
      </div>
    </header>
  );
}

