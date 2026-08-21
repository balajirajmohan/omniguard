import { Activity, KeyRound, Navigation, Radio, Route, Hash } from 'lucide-react';

function Row({ icon: Icon, label, value, tone }) {
  const colour = tone === 'bad' ? 'text-bad' : tone === 'ok' ? 'text-ok' : 'text-txt';
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-sunken/70 px-3 py-2.5">
      <span className="flex items-center gap-2 text-[11.5px] text-faint">
        <Icon size={12} aria-hidden="true" />{label}
      </span>
      <b className={`truncate font-mono text-[12.5px] tabular-nums ${colour}`}>{value ?? '—'}</b>
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
  const bridge = status.bridge ?? null;

  return (
    <aside className="card flex flex-col gap-2 p-4" aria-label="System telemetry">
      <h2 className="mb-1 flex items-center gap-2 text-[14px]">
        <Activity size={14} className="text-info" aria-hidden="true" />System state
      </h2>

      <Row icon={Radio} label="Robot" value={status.robot_status} />
      <Row icon={Navigation} label="Zone" value={status.robot_zone} />
      <Row icon={KeyRound} label="Credential" value={status.credential_status}
        tone={revoked ? 'bad' : status.credential_status ? 'ok' : undefined} />
      <Row icon={KeyRound} label="Agent" value={status.agent_status}
        tone={status.agent_status === 'QUARANTINED' ? 'bad' : undefined} />

      {/* Physical telemetry, reported by the backend from the secured bridge. */}
      <Row icon={Navigation} label="Position"
        value={robot ? `${robot.x.toFixed(2)}, ${robot.y.toFixed(2)}` : 'not reported'} />
      <Row icon={Route} label="Motion" value={bridge?.motion_state} />
      <Row icon={Hash} label="Last cmd"
        value={bridge?.last_command_id ? String(bridge.last_command_id).slice(0, 8) : null} />
      {status.last_containment_ack && (
        <Row icon={Radio} label="Containment" value={status.last_containment_ack} tone="bad" />
      )}

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
        Position comes from <span className="font-mono text-dim">isaac_bridge_state</span> — the
        browser never talks to the bridge. Driving into{' '}
        <span className="font-mono text-bad">RESTRICTED_ZONE</span> or outside the safe rectangles
        is refused by deterministic policy, for the operator as well as the attacker.
      </p>
    </aside>
  );
}
