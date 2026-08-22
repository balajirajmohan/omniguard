import { box, iso, pt, quad } from './isometric';
import { useReducedMotion } from '../../hooks/useMotionPrefs';
import type { Outcome } from '../../data/demoData';

/**
 * Compact warehouse twin used by the operations console. The robot's route and
 * halt point are derived from the active decision outcome.
 */
export function TwinMap({ outcome }: { outcome: Outcome }) {
  const reduced = useReducedMotion();
  const blocked = outcome === 'BLOCK' || outcome === 'ESTOP';

  // A denied command never leaves the staging aisle; an allowed one runs to ZONE_B.
  const robotPos = blocked ? { x: 2.2, y: 5.2 } : { x: 5.6, y: 1.6 };
  const robot = box(robotPos.x, robotPos.y, robotPos.x + 0.6, robotPos.y + 0.6, 15);

  const route = blocked
    ? `M${pt(1.2, 5.6, 3)} L${pt(2.5, 5.3, 3)}`
    : `M${pt(1.2, 5.6, 3)} L${pt(3.0, 4.2, 3)} L${pt(5.0, 2.4, 3)} L${pt(5.9, 1.9, 3)}`;

  const stroke = blocked ? '#ff5533' : '#22d3ee';
  const [hx, hy] = iso(6.3, 6.3, 6);

  return (
    <div className="relative aspect-[16/10] w-full">
      <svg viewBox="60 150 540 400" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <linearGradient id="og-map-floor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#101a26" />
            <stop offset="100%" stopColor="#080d14" />
          </linearGradient>
        </defs>

        <polygon points={quad(0, 0, 8, 8)} fill="url(#og-map-floor)" />

        <g stroke="#22d3ee" strokeOpacity="0.09" strokeWidth="0.8">
          {Array.from({ length: 9 }, (_, i) => {
            const [a, b] = iso(i, 0);
            const [c, d] = iso(i, 8);
            return <line key={`x${i}`} x1={a} y1={b} x2={c} y2={d} />;
          })}
          {Array.from({ length: 9 }, (_, i) => {
            const [a, b] = iso(0, i);
            const [c, d] = iso(8, i);
            return <line key={`y${i}`} x1={a} y1={b} x2={c} y2={d} />;
          })}
        </g>

        {/* Permitted zones */}
        <polygon
          points={quad(0.6, 0.6, 3.2, 3.0)}
          fill="#22d3ee"
          fillOpacity="0.05"
          stroke="#22d3ee"
          strokeOpacity="0.3"
          strokeWidth="1"
        />
        <polygon
          points={quad(4.8, 0.6, 7.4, 3.0)}
          fill="#22d3ee"
          fillOpacity="0.05"
          stroke="#22d3ee"
          strokeOpacity="0.3"
          strokeWidth="1"
        />
        {/* Human zone */}
        <polygon
          points={quad(4.4, 4.6, 7.4, 7.4)}
          fill="#ff5533"
          fillOpacity={blocked ? 0.14 : 0.08}
          stroke="#ff5533"
          strokeOpacity={blocked ? 0.7 : 0.42}
          strokeWidth="1.2"
          strokeDasharray="6 4"
        />

        {/* Racks */}
        {[box(0.6, 3.5, 3.2, 4.05, 26), box(4.8, 3.5, 7.4, 4.05, 26)].map((r, i) => (
          <g key={i}>
            <polygon points={r.left} fill="#0f1720" stroke="#243040" strokeWidth="0.8" />
            <polygon points={r.right} fill="#151f2c" stroke="#243040" strokeWidth="0.8" />
            <polygon points={r.top} fill="#1b2635" stroke="#2a3849" strokeWidth="0.9" />
          </g>
        ))}

        {/* Route */}
        <path
          d={route}
          fill="none"
          stroke={stroke}
          strokeOpacity="0.75"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="9 7"
          style={reduced ? undefined : { animation: 'og-dash 4s linear infinite' }}
        />

        {/* Human */}
        <g transform={`translate(${hx - 5}, ${hy - 30})`}>
          <circle cx="5" cy="5" r="4.2" fill="#ff8a6b" />
          <path d="M5 10.5c-3.4 0-5 2.2-5 5.6v6.2h10v-6.2c0-3.4-1.6-5.6-5-5.6Z" fill="#ff8a6b" />
          <path
            d="M2.4 22.3 1 30M7.6 22.3 9 30"
            stroke="#ff8a6b"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
        </g>

        {/* Robot */}
        <g>
          <polygon points={robot.left} fill="#12202c" stroke="#2a3849" strokeWidth="0.8" />
          <polygon points={robot.right} fill="#182a38" stroke="#2a3849" strokeWidth="0.8" />
          <polygon
            points={robot.top}
            fill={blocked ? '#3a1a16' : '#1d3242'}
            stroke={stroke}
            strokeWidth="1.3"
          />
        </g>
      </svg>

      <span className="pointer-events-none absolute left-[16%] top-[34%] font-mono text-[9.5px] tracking-[0.12em] text-ink-faint">
        ZONE_A
      </span>
      <span className="pointer-events-none absolute right-[18%] top-[34%] font-mono text-[9.5px] tracking-[0.12em] text-ink-faint">
        ZONE_B
      </span>
      <span className="pointer-events-none absolute bottom-[20%] right-[10%] font-mono text-[9.5px] tracking-[0.12em] text-deny/85">
        RESTRICTED_ZONE
      </span>
    </div>
  );
}
