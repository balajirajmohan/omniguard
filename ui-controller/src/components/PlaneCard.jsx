import { CheckCircle2, CircleDashed, PauseCircle, ShieldCheck, ShieldX, Skull, Clock } from 'lucide-react';

/* Never colour alone: each state carries an icon and a word as well as a hue. */
const LOOK = {
  idle:  { word: 'IDLE',       Icon: CircleDashed, text: 'text-faint', ring: 'border-line',    dot: 'bg-faint' },
  allow: { word: 'AUTHORIZED', Icon: CheckCircle2, text: 'text-ok',    ring: 'border-ok/55',   dot: 'bg-ok' },
  hold:  { word: 'HELD',       Icon: PauseCircle,  text: 'text-warn',  ring: 'border-warn/55', dot: 'bg-warn' },
  block: { word: 'BLOCKED',    Icon: ShieldX,      text: 'text-bad',   ring: 'border-bad/55',  dot: 'bg-bad' },
};

export default function PlaneCard({ panel, state }) {
  const hacker = panel === 'rogue';
  const look = LOOK[state.lamp] ?? LOOK.idle;
  const { Icon } = look;
  const Badge = hacker ? Skull : ShieldCheck;
  const accent = hacker ? 'text-bad' : 'text-ok';

  return (
    <section
      className={`card card-glow p-3 transition-colors duration-300 ${
        state.lamp === 'block' ? 'border-bad/50' : state.lamp === 'allow' ? 'border-ok/40' : ''}`}
      style={{ '--glow': hacker ? 'rgba(225,29,72,.45)' : 'rgba(5,150,105,.45)' }}
      aria-label={hacker ? 'Hacker control plane' : 'Valid operator control plane'}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="flex items-center gap-1.5 text-[13px]">
            <Badge size={13} className={accent} aria-hidden="true" />
            {hacker ? 'Hacker' : 'Valid Operator'}
          </h3>
          <p className="mt-0.5 truncate font-mono text-[10px] text-faint">
            {hacker ? 'rogue-controller' : 'fleet-controller-01'}
            {hacker && <span className="ml-1 text-warn">· stolen credential</span>}
          </p>
        </div>
        <span className={`flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-1
                          ${look.ring} ${look.text}`}>
          <span className={`size-1.5 rounded-full ${look.dot} ${state.lamp === 'block' ? 'a-pulse' : ''}`} />
          <Icon size={11} strokeWidth={2.5} aria-hidden="true" />
          <b className="text-[9.5px] tracking-[.1em]">{state.lampLabel ?? look.word}</b>
        </span>
      </header>

      <dl className="mt-2 grid grid-cols-3 gap-1.5">
        {[['speed', state.speed.toFixed(2)], ['zone', state.zone ?? '—'],
          ['setpoint', state.setpoint ? `${state.setpoint.x.toFixed(1)},${state.setpoint.y.toFixed(1)}` : '—']]
          .map(([k, v]) => (
            <div key={k} className="rounded-lg border border-line bg-sunken/70 px-2 py-1">
              <dt className="label">{k}</dt>
              <dd className="truncate font-mono text-[11.5px] tabular-nums">{v}</dd>
            </div>
          ))}
      </dl>

      {state.lease && (
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 rounded-lg border border-ok/35 bg-ok/5
                      px-2 py-1 font-mono text-[9.5px] text-ok">
          <Clock size={9} aria-hidden="true" />
          lease {String(state.lease.controlId).slice(0, 8)}
          {state.lease.maxSpeed != null && <span>· max {state.lease.maxSpeed}</span>}
        </p>
      )}

      {/* Reserved height: chips appearing must not shove the card's neighbours. */}
      <div className="mt-1.5 flex min-h-[20px] flex-wrap gap-1" role="status" aria-atomic="true">
        <span className="sr-only">
          {state.lamp === 'idle' ? 'Idle.' : `${state.lampLabel ?? look.word}. ${state.reasons.join(', ')}`}
        </span>
        {state.reasons.slice(0, 4).map((r) => (
          <span key={r} aria-hidden="true"
            className={`rounded-full border px-1.5 py-px font-mono text-[9px] ${
              state.lamp === 'allow' ? 'border-ok/45 bg-ok/10 text-ok'
                : state.lamp === 'hold' ? 'border-warn/45 bg-warn/10 text-warn'
                  : 'border-bad/45 bg-bad/10 text-bad'}`}>{r}</span>
        ))}
      </div>

      {state.ai && (
        <p className="mt-1 font-mono text-[9.5px] text-info/90">
          AI {state.ai.enforcement_mode ?? 'SHADOW_TELEOP'} · risk {state.ai.risk}
        </p>
      )}
    </section>
  );
}
