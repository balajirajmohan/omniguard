import {
  ARM_EXTENSION, ARM_YAW_DEGREES, floorBounds, headingFrom, isRestrictedZone,
} from '../lib/omniguard.js';

const SCALE = 10;

/* Top-down projection of the Franka arm, in metres. The real arm reaches about
 * 0.85 m; it is drawn longer so it stays legible at floor scale. */
const ARM_MAX_M = 2.2;
const JAW_LENGTH_M = 0.42;
/* GRIPPER_TARGETS in isaac/warehouse_robot_demo.py: open 0.04, close 0.0. */
const JAW_GAP_M = { open: 0.62, close: 0.16 };
/* Explicit joint targets carry no preset name, so the arm is drawn mid-pose. */
const NEUTRAL_EXTENSION = 0.6;
/* Nothing reported yet: park the arm folded rather than invent a reach. */
const PARKED_EXTENSION = 0.34;

export default function WarehouseMap({ zones, robot, target, trail, setpoints, manipulator }) {
  const bounds = floorBounds(zones);
  const [x0, y0, x1, y1] = bounds;
  const W = (x1 - x0) * SCALE;
  const H = (y1 - y0) * SCALE;
  const wx = (x) => (x - x0) * SCALE;
  const wy = (y) => (y1 - y) * SCALE;

  const arm = manipulator?.arm ?? null;
  const gripper = manipulator?.gripper ?? null;
  const armLabel = [arm?.preset ?? (arm ? 'joints' : null), gripper?.action]
    .filter(Boolean).join(' \u00b7 ');
  /* Three states, and the label always says which one:
   *   confirmed  isaac_bridge_state echoed the pose back
   *   commanded  the backend accepted it, Isaac has not confirmed it
   *   idle       nothing reported -- the arm is drawn parked and dimmed, so the
   *              chassis is still visible without implying a known pose. */
  const confirmed = arm?.source === 'confirmed' || gripper?.source === 'confirmed';
  const known = Boolean(arm || gripper);

  /* Two equal links, solved as a planar 2-link arm: the further the preset
   * reaches, the straighter the elbow -- which is what the real manipulator
   * does. Top-down, so the bend is drawn as lateral offset. */
  let armGeom = null;
  if (robot) {
    const extension = arm
      ? (ARM_EXTENSION[arm.preset] ?? NEUTRAL_EXTENSION)
      : PARKED_EXTENSION;
    const yaw = headingFrom(robot, target, trail)
      + ((ARM_YAW_DEGREES[arm?.preset] ?? 0) * Math.PI) / 180;
    const cos = Math.cos(yaw);
    const sin = Math.sin(yaw);
    const nx = -sin;
    const ny = cos;

    const link = ARM_MAX_M / 2;
    const reach = Math.max(0.1, Math.min(ARM_MAX_M, ARM_MAX_M * extension));
    const wrist = { x: robot.x + cos * reach, y: robot.y + sin * reach };
    /* Elbow rides the perpendicular bisector; height falls to zero as the arm
     * straightens out, so no special case is needed at full reach. */
    const lift = Math.sqrt(Math.max(0, link * link - (reach / 2) * (reach / 2)));
    const elbow = {
      x: robot.x + cos * (reach / 2) + nx * lift,
      y: robot.y + sin * (reach / 2) + ny * lift,
    };

    const half = (JAW_GAP_M[gripper?.action] ?? JAW_GAP_M.close) / 2;
    const jaw = (sign) => ({
      base: { x: wrist.x + nx * half * sign, y: wrist.y + ny * half * sign },
      tip: {
        x: wrist.x + nx * half * sign + cos * JAW_LENGTH_M,
        y: wrist.y + ny * half * sign + sin * JAW_LENGTH_M,
      },
    });
    armGeom = { elbow, wrist, jaws: [jaw(1), jaw(-1)] };
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={robot
        ? `Warehouse floor. Robot at ${robot.x.toFixed(1)}, ${robot.y.toFixed(1)} metres.`
          + (armLabel
            ? ` Arm and gripper: ${armLabel}, ${confirmed ? 'confirmed by Isaac' : 'commanded, not yet confirmed'}.`
            : '')
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

          {/* Manipulator, in the livery of the reference robot: charcoal base
              and joints, orange links, bare-metal jaws. Dimmed while no arm
              state has been reported, and labelled so the pose is never
              mistaken for something Isaac confirmed. */}
          {armGeom && (
            <g opacity={known ? 1 : 0.45} strokeLinecap="round">
              {/* mounting plate + turret */}
              <circle cx={wx(robot.x)} cy={wy(robot.y)} r={0.40 * SCALE}
                fill="var(--color-robot-dark)" stroke="rgba(0,0,0,.5)" strokeWidth="0.5" />

              {/* upper arm -> elbow -> forearm */}
              <line x1={wx(robot.x)} y1={wy(robot.y)} x2={wx(armGeom.elbow.x)} y2={wy(armGeom.elbow.y)}
                stroke="var(--color-robot-dark)" strokeWidth={0.42 * SCALE} />
              <line x1={wx(robot.x)} y1={wy(robot.y)} x2={wx(armGeom.elbow.x)} y2={wy(armGeom.elbow.y)}
                stroke="var(--color-robot)" strokeWidth={0.32 * SCALE}
                strokeDasharray={confirmed || !known ? undefined : '2.5 1.6'} />
              <line x1={wx(armGeom.elbow.x)} y1={wy(armGeom.elbow.y)}
                x2={wx(armGeom.wrist.x)} y2={wy(armGeom.wrist.y)}
                stroke="var(--color-robot-dark)" strokeWidth={0.32 * SCALE} />
              <line x1={wx(armGeom.elbow.x)} y1={wy(armGeom.elbow.y)}
                x2={wx(armGeom.wrist.x)} y2={wy(armGeom.wrist.y)}
                stroke="var(--color-robot)" strokeWidth={0.22 * SCALE}
                strokeDasharray={confirmed || !known ? undefined : '2.5 1.6'} />

              {/* joints */}
              <circle cx={wx(armGeom.elbow.x)} cy={wy(armGeom.elbow.y)} r={0.26 * SCALE}
                fill="var(--color-robot-dark)" stroke="var(--color-robot-hi)" strokeWidth="0.6" />
              <circle cx={wx(armGeom.wrist.x)} cy={wy(armGeom.wrist.y)} r={0.18 * SCALE}
                fill="var(--color-robot-dark)" stroke="var(--color-robot-hi)" strokeWidth="0.5" />

              {/* two-finger gripper: the gap is the open/close read-out */}
              {armGeom.jaws.map((j, i) => (
                <g key={i}>
                  <line x1={wx(armGeom.wrist.x)} y1={wy(armGeom.wrist.y)}
                    x2={wx(j.base.x)} y2={wy(j.base.y)}
                    stroke="var(--color-steel)" strokeWidth={0.1 * SCALE} />
                  <line x1={wx(j.base.x)} y1={wy(j.base.y)} x2={wx(j.tip.x)} y2={wy(j.tip.y)}
                    stroke="var(--color-steel)" strokeWidth={0.14 * SCALE} />
                </g>
              ))}

              <text x={wx(armGeom.wrist.x) + 6} y={wy(armGeom.wrist.y) + 9}
                fill={known ? 'var(--color-robot-hi)' : 'var(--color-faint)'} fontSize="4.4"
                fontFamily="ui-monospace, monospace">
                {known ? `${armLabel}${confirmed ? '' : ' cmd'}` : 'arm idle'}
              </text>
            </g>
          )}

          {/* turret cap, drawn last so the links emerge from under it */}
          <circle cx={wx(robot.x)} cy={wy(robot.y)} r={0.24 * SCALE} fill="var(--color-robot)"
            stroke="var(--color-robot-dark)" strokeWidth="0.8" />
          <circle cx={wx(robot.x)} cy={wy(robot.y)} r="1.1" fill="var(--color-robot-dark)" />
        </>
      ) : (
        /* No invented origin: if the backend has not reported a pose, say so. */
        <text x={W / 2} y={H / 2} textAnchor="middle" fill="var(--color-faint)" fontSize="6"
          fontFamily="ui-monospace, monospace">awaiting isaac_bridge_state.position</text>
      )}
    </svg>
  );
}
