import { CheckCircle2, CircleDashed, PauseCircle, ShieldX } from 'lucide-react';

/* Never colour alone: every state carries an icon and a word as well as a hue. */
const LOOK = {
  idle:  { label: 'IDLE',       Icon: CircleDashed, text: 'text-faint', ring: 'border-line',      dot: 'bg-faint' },
  allow: { label: 'AUTHORIZED', Icon: CheckCircle2, text: 'text-ok',    ring: 'border-ok/60',     dot: 'bg-ok'    },
  hold:  { label: 'HELD',       Icon: PauseCircle,  text: 'text-warn',  ring: 'border-warn/60',   dot: 'bg-warn'  },
  block: { label: 'BLOCKED',    Icon: ShieldX,      text: 'text-bad',   ring: 'border-bad/60',    dot: 'bg-bad'   },
};

export default function StatusLamp({ state = 'idle', label }) {
  const look = LOOK[state] ?? LOOK.idle;
  const { Icon } = look;
  const tint = state === 'idle' ? '' : state === 'allow' ? 'bg-ok/10' : state === 'hold' ? 'bg-warn/10' : 'bg-bad/10';

  return (
    <div className={`flex shrink-0 items-center gap-2.5 rounded-full border px-3.5 py-1.5
                     transition-colors duration-200 ${look.ring} ${look.text} ${tint}`}>
      <span className="relative flex size-2.5 shrink-0">
        {state === 'block' && <span className={`a-ping absolute inset-0 rounded-full ${look.dot}`} />}
        <span className={`relative size-2.5 rounded-full ${look.dot} ${state === 'block' ? 'a-pulse' : ''}`}
          style={state !== 'idle' ? { boxShadow: '0 0 10px currentColor' } : undefined} />
      </span>
      <Icon size={13} strokeWidth={2.5} aria-hidden="true" />
      <b className="text-[11px] font-bold tracking-[.12em]">{label ?? look.label}</b>
    </div>
  );
}
