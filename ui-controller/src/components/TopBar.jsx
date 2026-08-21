import { Cpu, Gamepad2, RotateCcw, Settings, Zap } from 'lucide-react';

export default function TopBar({ status, health, onReset, onToggleSettings, pad, resetting, settingsOpen }) {
  const online = status.robot_status !== 'API DOWN';
  const ai = health?.anomaly;
  return (
    <header className="mb-3 flex flex-wrap items-center gap-4">
      <div className="flex min-w-[250px] items-center gap-3">
        <div className="relative grid size-10 shrink-0 place-items-center rounded-xl"
          style={{
            background: 'conic-gradient(from 140deg,#1E3A5F,#059669,#60A5FA,#1E3A5F)',
            boxShadow: '0 0 26px -4px rgba(5,150,105,.6)',
          }}>
          <Zap size={17} className="text-white" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-[19px] leading-tight">OmniGuard</h1>
          <p className="text-[11.5px] text-faint">Dual control plane · live teleop into Isaac Sim</p>
        </div>
      </div>

      <div className="flex flex-1 items-center gap-2">
        <span className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold
                          ${online ? 'border-ok/50 bg-ok/10 text-ok' : 'border-bad/50 bg-bad/10 text-bad'}`}>
          <span className="relative flex size-2">
            <span className={`absolute inset-0 rounded-full ${online ? 'bg-ok a-ping' : 'bg-bad'}`} />
            <span className={`relative size-2 rounded-full ${online ? 'bg-ok' : 'bg-bad'}`} />
          </span>
          {online ? 'BROKER LIVE' : 'BROKER DOWN'}
        </span>
        <span className={`hidden items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] sm:flex
                          ${status.bridge ? 'border-line text-dim' : 'border-bad/50 text-bad'}`}>
          bridge {status.bridge ? 'reachable' : 'unreachable'}
        </span>
        {ai && (
          /* Model provenance up front: version, artifact integrity, and the fact
           * that the model does not actuate anything. */
          <span title={`artifact ${ai.artifact_verified ? 'verified' : 'UNVERIFIED'} · ${ai.n_training_samples} samples`}
            className={`hidden items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] md:flex
                        ${ai.degraded ? 'border-warn/50 text-warn' : 'border-line text-dim'}`}>
            <Cpu size={12} aria-hidden="true" />
            {ai.model_version}{ai.degraded ? ' · degraded' : ''} · advisory only
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span className="hidden items-center gap-1.5 text-[11px] text-faint lg:flex">
          <Gamepad2 size={13} aria-hidden="true" />{pad}
        </span>
        <button onClick={onToggleSettings} aria-expanded={settingsOpen} className="btn">
          <Settings size={14} aria-hidden="true" />Settings
        </button>
        <button onClick={onReset} disabled={resetting} className="btn btn-primary">
          <RotateCcw size={14} aria-hidden="true" className={resetting ? 'animate-spin' : ''} />
          {resetting ? 'Resetting' : 'Reset demo'}
        </button>
      </div>
    </header>
  );
}
