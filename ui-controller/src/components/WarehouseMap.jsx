import { floorBounds, isRestrictedZone } from '../lib/omniguard.js';

const SCALE = 10;

export default function WarehouseMap({ zones, robot, target, trail, setpoints }) {
  const bounds = floorBounds(zones);
  const [x0, y0, x1, y1] = bounds;
  const W = (x1 - x0) * SCALE;
  const H = (y1 - y0) * SCALE;
  const wx = (x) => (x - x0) * SCALE;
  const wy = (y) => (y1 - y) * SCALE;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={robot
        ? `Warehouse floor. Robot at ${robot.x.toFixed(1)}, ${robot.y.toFixed(1)} metres.`
        : 'Warehouse floor. Robot position not yet reported by the backend.'}
      preserveAspectRatio="xMidYMid meet"
      className="block h-full max-h-full w-full rounded-xl border border-line bg-sunken">
      <defs>
        <pattern id="grid" width={2 * SCALE} height={2 * SCALE} patternUnits="userSpaceOnUse">
          <path d={`M ${2 * SCALE} 0 L 0 0 0 ${2 * SCALE}`} fill="none"
            stroke="rgba(255,255,255,.045)" strokeWidth="0.5" />
        </pattern>
        <pattern id="hazard" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="rgba(220,38,38,.13)" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(220,38,38,.30)" strokeWidth="2.4" />
        </pattern>
        <radialGradient id="bot">
          <stop offset="0%" stopColor="var(--color-info)" stopOpacity=".6" />
          <stop offset="100%" stopColor="var(--color-info)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect width={W} height={H} fill="url(#grid)" />

      {Object.entries(zones ?? {}).map(([name, r]) => {
        const restricted = isRestrictedZone(name);
        const stroke = restricted ? 'var(--color-bad)' : 'var(--color-ok)';
        return (
          <g key={name}>
            <rect x={wx(r.x_min)} y={wy(r.y_max)}
              width={(r.x_max - r.x_min) * SCALE} height={(r.y_max - r.y_min) * SCALE} rx="3"
              fill={restricted ? 'url(#hazard)' : 'rgba(5,150,105,.10)'}
              stroke={stroke} strokeWidth="0.7" strokeDasharray={restricted ? '3 2' : undefined} />
            <text x={wx(r.x_min) + 4} y={wy(r.y_max) + 10} fill={stroke} fontSize="5"
              fontFamily="ui-monospace, monospace">{name}</text>
          </g>
        );
      })}

      {trail?.length > 1 && (
        <polyline points={trail.map((p) => `${wx(p.x)},${wy(p.y)}`).join(' ')}
          fill="none" stroke="var(--color-info)" strokeWidth="1" strokeOpacity=".4"
          strokeLinecap="round" strokeLinejoin="round" />
      )}

      {/* Where the backend last told Isaac to go. */}
      {target && (
        <g>
          <circle cx={wx(target.x)} cy={wy(target.y)} r="4" fill="none"
            stroke="var(--color-info)" strokeWidth="0.8" strokeDasharray="2 2" />
          <text x={wx(target.x) + 6} y={wy(target.y) - 4} fill="var(--color-info)"
            fontSize="4.4" fontFamily="ui-monospace, monospace">target</text>
        </g>
      )}

      {robot && setpoints?.map(({ id, sp }) => {
        const colour = id === 'legit' ? 'var(--color-ok)' : 'var(--color-bad)';
        return (
          <g key={id}>
            <line x1={wx(robot.x)} y1={wy(robot.y)} x2={wx(sp.x)} y2={wy(sp.y)}
              stroke={colour} strokeWidth="0.8" strokeDasharray="2 2" strokeOpacity=".9" />
            <circle cx={wx(sp.x)} cy={wy(sp.y)} r="3.4" fill="none" stroke={colour} strokeWidth="1" />
            <text x={wx(sp.x) + 5} y={wy(sp.y) - 4} fill={colour} fontSize="4.4"
              fontFamily="ui-monospace, monospace">{id === 'legit' ? 'OP' : 'ROGUE'}</text>
          </g>
        );
      })}

      {robot ? (
        <>
          <circle cx={wx(robot.x)} cy={wy(robot.y)} r="10" fill="url(#bot)" />
          <circle cx={wx(robot.x)} cy={wy(robot.y)} r="3.2" fill="var(--color-info)"
            stroke="var(--color-bg)" strokeWidth="0.9" />
        </>
      ) : (
        /* No invented origin: if the backend has not reported a pose, say so. */
        <text x={W / 2} y={H / 2} textAnchor="middle" fill="var(--color-faint)" fontSize="6"
          fontFamily="ui-monospace, monospace">awaiting isaac_bridge_state.position</text>
      )}
    </svg>
  );
}
