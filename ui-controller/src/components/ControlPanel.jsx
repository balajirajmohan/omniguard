import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Crosshair, Gauge, MapPin, ShieldCheck, Skull } from 'lucide-react';
import Joystick from './Joystick.jsx';
import StatusLamp from './StatusLamp.jsx';
import VerdictLog from './VerdictLog.jsx';

/* Flashes when the value changes, so a number moving in a dense grid is
 * noticeable without being animated the whole time. */
function Readout({ icon: Icon, label, value, unit, mono = true }) {
  const [flash, setFlash] = useState(false);
  const prev = useRef(value);
  useEffect(() => {
    if (prev.current === value) return;
    prev.current = value;
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 560);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <div className={`rounded-xl border border-line bg-sunken/70 px-3 py-2 ${flash ? 'a-flash' : ''}`}>
      <span className="label mb-0.5 flex items-center gap-1.5">
        <Icon size={10} aria-hidden="true" />{label}
      </span>
      <b className={`text-[15px] ${mono ? 'font-mono tabular-nums' : ''}`}>{value}</b>
      {unit && <span className="ml-1 text-[11px] text-faint">{unit}</span>}
    </div>
  );
}

function Toggle({ checked, onChange, tone, title, hint }) {
  const on = tone === 'bad'
    ? 'border-bad/60 bg-bad/10 text-bad'
    : 'border-warn/60 bg-warn/10 text-warn';
  return (
    <label className={`flex cursor-pointer items-start gap-2.5 rounded-xl border bg-sunken/70 px-3 py-2
                       transition-colors duration-200 hover:border-line-hi
                       ${checked ? on : 'border-line text-dim'}`}>
      <input
        type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className={`mt-0.5 size-3.5 cursor-pointer ${tone === 'bad' ? 'accent-[#DC2626]' : 'accent-[#FBBF24]'}`}
      />
      <span className="min-w-0">
        <b className="block text-[12px] font-semibold">{title}</b>
        <span className="block text-[11px] text-faint">{hint}</span>
      </span>
    </label>
  );
}

export default function ControlPanel({ panel, state, onStick, external, options, setOptions }) {
  const rogue = panel === 'rogue';
  const tone = rogue ? 'bad' : 'ok';
  const blocked = state.lamp === 'block';
  const Badge = rogue ? Skull : ShieldCheck;

  return (
    <section
      aria-label={rogue ? 'Rogue controller' : 'Fleet operator'}
      className={`card relative overflow-hidden p-5 transition-colors duration-300
                  ${blocked ? 'border-bad/60' : state.lamp === 'allow' ? 'border-ok/50' : ''}`}
      style={blocked
        ? { boxShadow: '0 0 48px -16px rgba(220,38,38,.55), inset 0 0 0 1px rgba(220,38,38,.22)' }
        : undefined}
    >
      {/* identity stripe */}
      <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r to-transparent
                       ${rogue ? 'from-bad-solid' : 'from-ok-solid'}`} />
      {blocked && (
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px overflow-hidden">
          <div className="a-sweep h-px w-1/3 bg-bad" />
        </div>
      )}

      <header className="mb-5 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-[16px]">
            <span className={`grid size-7 shrink-0 place-items-center rounded-lg border
                              ${rogue ? 'border-bad/40 bg-bad/10 text-bad' : 'border-ok/40 bg-ok/10 text-ok'}`}>
              <Badge size={14} aria-hidden="true" />
            </span>
            {rogue ? 'Rogue Controller' : 'Fleet Operator'}
          </h3>
          <dl className="mt-2 space-y-1 text-[11.5px]">
            <div className="flex gap-2">
              <dt className="w-[52px] shrink-0 text-faint">agent</dt>
              <dd className="font-mono text-dim">
                fleet-agent-01
                {rogue && <span className="ml-1.5 rounded bg-warn/15 px-1.5 py-px text-[10px] text-warn">stolen</span>}
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-[52px] shrink-0 text-faint">device</dt>
              <dd className={`font-mono ${rogue ? 'text-bad' : 'text-dim'}`}>
                {rogue ? 'rogue-controller' : 'fleet-controller-01'}
              </dd>
            </div>
          </dl>
        </div>
        <StatusLamp state={state.lamp} label={state.lampLabel} />
      </header>

      <div className="flex flex-wrap items-start gap-5">
        <Joystick
          tone={tone}
          onChange={onStick}
          external={external}
          label={`${rogue ? 'Rogue' : 'Operator'} joystick — arrow keys or WASD to drive`}
        />
        <div className="grid min-w-[164px] flex-1 gap-2">
          <Readout icon={Gauge} label="Speed" value={state.speed.toFixed(2)} unit="m/s" />
          <Readout icon={MapPin} label="Target zone" value={state.zone ?? '—'} />
          <Readout icon={Crosshair} label="Setpoint"
            value={state.setpoint ? `${state.setpoint.x.toFixed(1)}, ${state.setpoint.y.toFixed(1)}` : '—'} />
        </div>
      </div>

      {rogue && (
        <div className="mt-8 grid gap-2">
          <Toggle
            checked={options.overspeed} onChange={(v) => setOptions({ ...options, overspeed: v })} tone="warn"
            title="Overspeed" hint="Ignore the 1.5 m/s governor a real client would honour"
          />
          <Toggle
            checked={options.bypass} onChange={(v) => setOptions({ ...options, bypass: v })} tone="bad"
            title="Bypass broker" hint="Skip OmniGuard and drive :8899 directly"
          />
        </div>
      )}

      {/* Fixed-height slot: verdict chips appearing must not shove the log down. */}
      <div className={`slot mt-4 ${rogue ? '' : 'mt-8'}`} style={{ '--slot-h': '30px' }}>
        <div role="status" aria-atomic="true" className="flex flex-wrap gap-1.5">
          <span className="sr-only">
            {state.lamp === 'idle' ? 'Idle.' : `${state.lampLabel ?? state.lamp}. ${state.reasons.join(', ')}`}
          </span>
          {state.reasons.map((r) => (
            <span key={r} aria-hidden="true"
              className={`a-rise rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] tracking-wide
                          ${state.lamp === 'allow'
                            ? 'border-ok/50 bg-ok/10 text-ok'
                            : state.lamp === 'hold'
                              ? 'border-warn/50 bg-warn/10 text-warn'
                              : 'border-bad/50 bg-bad/10 text-bad'}`}>
              {r}
            </span>
          ))}
        </div>
      </div>

      {rogue && options.bypass && (
        <p className="a-rise mt-2 flex items-start gap-2 rounded-xl border border-bad/50 bg-bad/10 px-3 py-2
                      text-[11.5px] text-bad">
          <AlertTriangle size={13} className="mt-px shrink-0" aria-hidden="true" />
          The policy engine is not being consulted. This is exactly why port 8899 must never be
          reachable from outside the GPU host.
        </p>
      )}

      <VerdictLog entries={state.log} />
    </section>
  );
}
