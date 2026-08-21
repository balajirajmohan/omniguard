import { Activity, KeyRound, Navigation, Radio } from 'lucide-react';

function Row({ icon: Icon, label, value, tone }) {
  const colour = tone === 'bad' ? 'text-bad' : tone === 'ok' ? 'text-ok' : 'text-txt';
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-sunken/70 px-3 py-2.5">
      <span className="flex items-center gap-2 text-[11.5px] text-faint">
        <Icon size={12} aria-hidden="true" />{label}
      </span>
      <b className={`font-mono text-[12.5px] tabular-nums ${colour}`}>{value ?? '—'}</b>
    </div>
  );
}

const LEGEND = [
  ['safe', 'border-ok bg-ok/25', 'rounded-sm'],
  ['restricted', 'border-bad bg-bad/25', 'rounded-sm'],
  ['robot', 'border-info bg-info', 'rounded-full'],
  ['setpoint', 'border-warn', 'rounded-full'],
];

export default function TelemetryRail({ status, robot }) {
  const revoked = status.credential_status === 'REVOKED';
  return (
    <aside className="card flex flex-col gap-2 p-4" aria-label="System telemetry">
      <h3 className="mb-1 flex items-center gap-2 text-[14px]">
        <Activity size={14} className="text-info" aria-hidden="true" />System state
      </h3>

      <Row icon={Radio} label="Robot" value={status.robot_status} />
      <Row icon={Navigation} label="Zone" value={status.robot_zone} />
      <Row icon={KeyRound} label="Credential" value={status.credential_status}
        tone={revoked ? 'bad' : status.credential_status ? 'ok' : undefined} />
      <Row icon={Navigation} label="Position"
        value={`${robot.x.toFixed(1)}, ${robot.y.toFixed(1)}`} />

      <div className="mt-1 rounded-xl border border-line bg-sunken/70 p-3">
        <span className="label mb-2">Map legend</span>
        <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px] text-dim">
          {LEGEND.map(([name, cls, shape]) => (
            <li key={name} className="flex items-center gap-1.5">
              <i className={`size-2.5 shrink-0 border ${cls} ${shape}`} aria-hidden="true" />{name}
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-auto pt-2 text-[11px] leading-relaxed text-faint">
        Position is dead-reckoned in the browser — the Isaac bridge has no pose readback yet, so this
        tracks commanded motion, not ground truth. Driving left or right stays in policy; driving up
        past <span className="font-mono text-dim">y = 5</span> enters{' '}
        <span className="font-mono text-bad">RESTRICTED_ZONE</span> and is blocked even for the operator.
      </p>
    </aside>
  );
}
