import { FLOOR, RESTRICTED, SAFE } from '../lib/omniguard.js';

const SCALE = 10;
const W = (FLOOR[2] - FLOOR[0]) * SCALE;
const H = (FLOOR[3] - FLOOR[1]) * SCALE;
const wx = (x) => (x - FLOOR[0]) * SCALE;
const wy = (y) => (FLOOR[3] - y) * SCALE;

function Zone({ name, rect, restricted }) {
  const [x0, y0, x1, y1] = rect;
  const stroke = restricted ? 'var(--color-bad)' : 'var(--color-ok)';
  return (
    <g>
      <rect
        x={wx(x0)} y={wy(y1)} width={(x1 - x0) * SCALE} height={(y1 - y0) * SCALE} rx="3"
        fill={restricted ? 'url(#hazard)' : 'rgba(5,150,105,.10)'}
        stroke={stroke} strokeWidth="0.7" strokeDasharray={restricted ? '3 2' : undefined}
      />
      {/* Text label, not colour alone, identifies each zone. */}
      <text x={wx(x0) + 4} y={wy(y1) + 10} fill={stroke} fontSize="5"
        fontFamily="ui-monospace, monospace" letterSpacing=".3">{name}</text>
    </g>
  );
}

export default function WarehouseMap({ robot, trail, setpoints }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Warehouse floor. Robot at ${robot.x.toFixed(1)}, ${robot.y.toFixed(1)} metres.`}
      className="block h-auto w-full rounded-xl border border-line bg-sunken">
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
        <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--color-info)" stopOpacity=".28" />
          <stop offset="100%" stopColor="var(--color-info)" stopOpacity="0" />
        </linearGradient>
      </defs>

      <rect width={W} height={H} fill="url(#grid)" />

      {/* slow radar sweep — ambient "this is live" signal */}
      <g className="a-radar" style={{ transformOrigin: `${wx(robot.x)}px ${wy(robot.y)}px` }}>
        <path d={`M ${wx(robot.x)} ${wy(robot.y)} L ${wx(robot.x) + 90} ${wy(robot.y) - 34}
                  A 96 96 0 0 1 ${wx(robot.x) + 90} ${wy(robot.y) + 34} Z`} fill="url(#sweep)" />
      </g>

      {Object.entries(SAFE).map(([n, r]) => <Zone key={n} name={n} rect={r} />)}
      {Object.entries(RESTRICTED).map(([n, r]) => <Zone key={n} name={n} rect={r} restricted />)}

      {trail.length > 1 && (
        <polyline points={trail.map((p) => `${wx(p.x)},${wy(p.y)}`).join(' ')}
          fill="none" stroke="var(--color-info)" strokeWidth="1" strokeOpacity=".4"
          strokeLinecap="round" strokeLinejoin="round" />
      )}

      {setpoints.map(({ id, sp }) => {
        const colour = id === 'legit' ? 'var(--color-ok)' : 'var(--color-bad)';
        return (
          <g key={id}>
            <line x1={wx(robot.x)} y1={wy(robot.y)} x2={wx(sp.x)} y2={wy(sp.y)}
              stroke={colour} strokeWidth="0.8" strokeDasharray="2 2" strokeOpacity=".9" />
            <circle cx={wx(sp.x)} cy={wy(sp.y)} r="3.4" fill="none" stroke={colour} strokeWidth="1" />
            <circle cx={wx(sp.x)} cy={wy(sp.y)} r="1" fill={colour} />
            <text x={wx(sp.x) + 5} y={wy(sp.y) - 4} fill={colour} fontSize="4.4"
              fontFamily="ui-monospace, monospace">{id === 'legit' ? 'OP' : 'ROGUE'}</text>
          </g>
        );
      })}

      <circle cx={wx(robot.x)} cy={wy(robot.y)} r="10" fill="url(#bot)" />
      <circle cx={wx(robot.x)} cy={wy(robot.y)} r="3.2" fill="var(--color-info)"
        stroke="var(--color-bg)" strokeWidth="0.9" />
    </svg>
  );
}
