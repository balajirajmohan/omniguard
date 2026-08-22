import { useCallback, useEffect, useRef, useState } from 'react';
import DualSenseShell from './DualSenseShell.jsx';

/* A DualSense, wired as a real control surface.
 *
 * The shell is the supplied vector artwork (DualSenseShell.jsx); everything
 * interactive is overlaid on top in the artwork's own coordinate space. Hand
 * tracing the silhouette never read as a DualSense, so the artwork is the
 * source of truth for shape and this file only places hit targets on it.
 *
 * The pad is split down the middle, which is the whole demo:
 *   left half  -> valid operator   left stick, d-pad, L1/L2
 *   right half -> hacker           right stick, face buttons, R1/R2
 *
 * All three input routes converge here. Pointer drag is handled locally;
 * keyboard and gamepad arrive through `stickRef`, which the controller reads on
 * its own animation frame so 60 Hz of stick motion never re-renders React.
 *
 * The light bars either side of the touchpad carry each plane's live verdict —
 * the same information as the lamps, in the place a PS5 actually shows state.
 */

/* Geometry is the artwork's coordinate space: the controller occupies roughly
 * x 293-1816, y 505-1564 of a 2100 square. The viewBox adds room above for the
 * gripper buttons and below for the footer. */
const VB = { x: 250, y: 360, w: 1620, h: 1330 };
const TRAVEL = 48; // thumb travel inside the stick well, in artwork units
const STICKS = {
  legit: { cx: 817, cy: 1052 },
  rogue: { cx: 1288, cy: 1052 },
};

const TONE = {
  idle: 'var(--color-faint)',
  allow: 'var(--color-ok)',
  hold: 'var(--color-warn)',
  block: 'var(--color-bad)',
};

const PLANE_TONE = { legit: 'var(--color-ok)', rogue: 'var(--color-bad)' };

/* Each cluster carries one plane's arm presets. Centres match the shapes the
 * artwork already draws, so the hit target sits on the button you can see. */
const DPAD = [
  { preset: 'reach', cx: 582, cy: 755, glyph: 'up', hotkey: '1' },
  { preset: 'stow', cx: 582, cy: 905, glyph: 'down', hotkey: '2' },
  { preset: 'carry', cx: 507, cy: 830, glyph: 'left', hotkey: '3' },
  { preset: 'inspect', cx: 657, cy: 830, glyph: 'right', hotkey: '4' },
];
const DPAD_HIT = 60; // half-size of each d-pad key's hit square

const FACES = [
  { preset: 'reach', cx: 1529, cy: 724, glyph: 'triangle', hotkey: '7' },
  { preset: 'carry', cx: 1419, cy: 833, glyph: 'square', hotkey: '9' },
  { preset: 'inspect', cx: 1643, cy: 833, glyph: 'circle', hotkey: '0' },
  { preset: 'stow', cx: 1529, cy: 946, glyph: 'cross', hotkey: '8' },
];
const FACE_R = 58;

/* Preset names sit in the clear shell either side of the stick bay. */
const LEGEND_Y = [1005, 1065, 1125, 1185];
const LEGEND_LEFT = 352;
const LEGEND_RIGHT = 1752;

/* The artwork's own shoulder tabs are tiny, so the gripper gets labelled
 * buttons above the shell — left pair operator, right pair hacker. */
const SHOULDERS = [
  { key: 'l2', x: 392, y: 372, w: 286, h: 58, action: 'close', panel: 'legit',
    label: 'L2 CLOSE', hotkey: 'E' },
  { key: 'l1', x: 366, y: 438, w: 338, h: 64, action: 'open', panel: 'legit',
    label: 'L1 OPEN', hotkey: 'Q' },
  { key: 'r2', x: 1442, y: 372, w: 286, h: 58, action: 'close', panel: 'rogue',
    label: 'R2 CLOSE', hotkey: 'P' },
  { key: 'r1', x: 1416, y: 438, w: 338, h: 64, action: 'open', panel: 'rogue',
    label: 'R1 OPEN', hotkey: 'O' },
];

/* Touchpad, lifted verbatim from the artwork so the emergency stop sits exactly
 * on the pad's own shape instead of a rectangle that overhangs it. Clicking it
 * is the emergency stop, as on a real pad — and a far larger target than the
 * Circle button it replaced. */
const TOUCHPAD_PATH =
  'M 1057.65 880.77 L 1252.63 880.77 C 1252.63 880.77 1305.45 882.79 1319 840.45'
  + ' C 1332.55 798.1 1372 608 1372 608 C 1372 608 1380.88 586.39 1352.73 578.33'
  + ' C 1324.58 570.26 990.4 542.03 756.84 578.33 C 727.85 582.83 737.02 610.59 737.02 610.59'
  + ' C 737.02 610.59 771.45 804.15 785 846.5 C 798.55 888.84 856.93 880.77 856.93 880.77 Z';
const TOUCHPAD_MID = { x: 1054, y: 715 };

const ESTOP_HOTKEY = 'SPACE';
/* Ink for anything drawn on the white shell. The plane labels stay white
 * because they sit on the black centre section. */
const GLYPH = 'rgba(0,0,0,.55)';
const SHELL_INK = '#16161a';

/* PS face-button glyphs and d-pad arrows, drawn rather than typed so they do
 * not depend on a font that ships the symbols. */
function Glyph({ kind, cx, cy, r = 26, colour }) {
  /* JSX hands numeric-looking props through as strings, and the triangle is the
   * one branch that adds `r` to a coordinate rather than multiplying it -- so
   * without this `cx + r` concatenates and the glyph shoots off the canvas. */
  r = Number(r);
  const common = {
    fill: 'none', stroke: colour, strokeWidth: r * 0.26, strokeLinejoin: 'round',
  };
  if (kind === 'triangle') {
    return <path d={`M ${cx} ${cy - r} L ${cx + r} ${cy + r * 0.8} L ${cx - r} ${cy + r * 0.8} Z`} {...common} />;
  }
  if (kind === 'circle') return <circle cx={cx} cy={cy} r={r * 0.92} {...common} />;
  if (kind === 'square') {
    return <rect x={cx - r * 0.85} y={cy - r * 0.85} width={r * 1.7} height={r * 1.7} rx={r * 0.16} {...common} />;
  }
  if (kind === 'cross') {
    return (
      <g {...common} strokeLinecap="round">
        <line x1={cx - r * 0.8} y1={cy - r * 0.8} x2={cx + r * 0.8} y2={cy + r * 0.8} />
        <line x1={cx + r * 0.8} y1={cy - r * 0.8} x2={cx - r * 0.8} y2={cy + r * 0.8} />
      </g>
    );
  }
  const a = r * 0.8;
  const dirs = {
    up: `M ${cx} ${cy - a} L ${cx + a} ${cy + a * 0.7} L ${cx - a} ${cy + a * 0.7} Z`,
    down: `M ${cx} ${cy + a} L ${cx + a} ${cy - a * 0.7} L ${cx - a} ${cy - a * 0.7} Z`,
    left: `M ${cx - a} ${cy} L ${cx + a * 0.7} ${cy - a} L ${cx + a * 0.7} ${cy + a} Z`,
    right: `M ${cx + a} ${cy} L ${cx - a * 0.7} ${cy - a} L ${cx - a * 0.7} ${cy + a} Z`,
  };
  return <path d={dirs[kind]} fill={colour} />;
}

/* A keycap drawn on the pad, so every button says which key does the same
 * thing. Purely a label: the hit target is always the button underneath. */
function Key({ x, y, label, on, dark = false }) {
  const w = label.length * 19 + 26;
  return (
    <g pointerEvents="none">
      <rect x={x - w / 2} y={y - 24} width={w} height="48" rx="11"
        fill={on ? 'var(--color-info)' : dark ? 'rgba(0,0,0,.55)' : 'rgba(255,255,255,.9)'}
        stroke={on ? 'var(--color-info)' : 'rgba(0,0,0,.35)'} strokeWidth="3" />
      <text x={x} y={y + 11} textAnchor="middle" fontSize="26"
        fill={on ? '#04122e' : dark ? '#fff' : '#16161a'} fontFamily="ui-monospace, monospace">
        {label}
      </text>
    </g>
  );
}

export default function DualSense({
  stickRef, onStick, lamps, leases, disabled,
  onArmPreset, onGripper, onEmergencyStop,
}) {
  const svgRef = useRef(null);
  const thumbRefs = useRef({});
  const barRefs = useRef({});
  const dragging = useRef(null);
  const [activePanel, setActivePanel] = useState(null);
  const [pressed, setPressed] = useState(null);

  const armed = Boolean(leases?.legit || leases?.rogue);

  const fire = (key, run) => (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    if (disabled) return;
    setPressed(key);
    setTimeout(() => setPressed((k) => (k === key ? null : k)), 180);
    run();
  };

  /* Thumb position and light-bar brightness are both display-rate, so they are
   * written straight to the DOM rather than through React state.
   *
   * The bar's colour is the plane's verdict (React owns that, via `lamps`); its
   * brightness is how hard that plane's stick is being pushed. `data-base` is
   * how the two meet: React parks the resting brightness there, and this only
   * decides between resting and lit. */
  const place = useCallback((panel, vec) => {
    const t = thumbRefs.current[panel];
    const bar = barRefs.current[panel];
    if (t) t.setAttribute('transform', `translate(${vec.x * TRAVEL} ${-vec.y * TRAVEL})`);
    if (bar) {
      const live = Math.min(1, Math.hypot(vec.x, vec.y)) > 0.12;
      bar.style.opacity = live ? '1' : (bar.dataset.base ?? '0.22');
    }
  }, []);

  /* Mirror whatever the hook currently holds — keyboard, gamepad, or our own
   * drag once it has round-tripped through setStick. */
  useEffect(() => {
    let frame;
    const draw = () => {
      let live = null;
      for (const panel of Object.keys(STICKS)) {
        const s = stickRef?.current?.[panel];
        if (s) {
          place(panel, s.vec);
          if (s.mag > 0.12) live = panel;
        }
      }
      setActivePanel((prev) => (prev === live ? prev : live));
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [stickRef, place]);

  /* --------------------------------------------------------- pointer drag */
  const toViewBox = (ev) => {
    const rect = svgRef.current.getBoundingClientRect();
    const scale = VB.w / rect.width;
    return {
      x: VB.x + (ev.clientX - rect.left) * scale,
      y: VB.y + (ev.clientY - rect.top) * scale,
    };
  };

  const move = useCallback((ev) => {
    const drag = dragging.current;
    if (!drag || drag.pointerId !== ev.pointerId) return;
    const p = toViewBox(ev);
    const origin = STICKS[drag.panel];
    let dx = p.x - origin.cx;
    let dy = p.y - origin.cy;
    const dist = Math.hypot(dx, dy);
    if (dist > TRAVEL) { dx = (dx / dist) * TRAVEL; dy = (dy / dist) * TRAVEL; }
    onStick(drag.panel, {
      vec: { x: dx / TRAVEL, y: -dy / TRAVEL },   // screen y down -> world y up
      mag: Math.min(1, dist / TRAVEL),
    });
  }, [onStick]);

  const release = useCallback((ev) => {
    const drag = dragging.current;
    if (!drag || drag.pointerId !== ev.pointerId) return;
    dragging.current = null;
    onStick(drag.panel, { vec: { x: 0, y: 0 }, mag: 0 });
  }, [onStick]);

  const grab = (panel) => (ev) => {
    if (disabled) return;
    ev.preventDefault();
    dragging.current = { panel, pointerId: ev.pointerId };
    ev.currentTarget.setPointerCapture?.(ev.pointerId);
    move(ev);
  };

  /* Drawn over the artwork's static stick so the thumb can actually move. */
  const Stick = ({ panel }) => {
    const { cx, cy } = STICKS[panel];
    const colour = TONE[lamps?.[panel] ?? 'idle'];
    return (
      <g onPointerDown={grab(panel)} onPointerMove={move} onPointerUp={release}
        onPointerCancel={release} style={{ cursor: disabled ? 'not-allowed' : 'grab' }}>
        <circle cx={cx} cy={cy} r="135" fill="#242427" />
        <circle cx={cx} cy={cy} r="112" fill="#151517" />
        <g ref={(el) => { thumbRefs.current[panel] = el; }}
          style={{ transition: 'transform .08s linear' }}>
          <circle cx={cx} cy={cy} r="100" fill={`url(#thumb-${panel})`} stroke="rgba(0,0,0,.6)" strokeWidth="4" />
          <circle cx={cx} cy={cy} r="62" fill="#1c1c20" stroke="rgba(255,255,255,.07)" strokeWidth="4" />
          <ellipse cx={cx} cy={cy - 16} rx="52" ry="36" fill="rgba(255,255,255,.045)" />
        </g>
      </g>
    );
  };

  return (
    <svg ref={svgRef} viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`}
      className="block h-auto w-full select-none" role="group"
      aria-label="DualSense controller. Left half drives the valid operator: left stick moves, d-pad sets arm presets, L1 and L2 work the gripper. Right half drives the hacker: right stick, face buttons, R1 and R2. The touchpad is the emergency stop.">
      <defs>
        {Object.keys(STICKS).map((panel) => (
          <radialGradient key={panel} id={`thumb-${panel}`} cx="50%" cy="34%">
            <stop offset="0%" stopColor="#45454c" />
            <stop offset="100%" stopColor="#1b1b1f" />
          </radialGradient>
        ))}
        <filter id="ds-bar-glow" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="9" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* shoulders — gripper. Left pair operator, right pair hacker. */}
      {SHOULDERS.map((b) => {
        const tone = PLANE_TONE[b.panel];
        const on = pressed === b.key;
        return (
          <g key={b.key} onPointerDown={fire(b.key, () => onGripper?.(b.panel, b.action))}
            style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}>
            <title>
              {`Gripper ${b.action} for the ${b.panel === 'legit' ? 'valid operator' : 'hacker'}`
                + ` — ${b.label} or key ${b.hotkey}`}
            </title>
            <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={b.h / 2}
              fill={on ? tone : '#26262b'} stroke={tone} strokeWidth="3" strokeOpacity=".55" />
            <text x={b.x + b.w * 0.37} y={b.y + b.h / 2 + 10} textAnchor="middle"
              fontSize="29" fill={on ? '#04122e' : tone} fontFamily="ui-monospace, monospace"
              pointerEvents="none">{b.label}</text>
            <Key x={b.x + b.w - 52} y={b.y + b.h / 2} label={b.hotkey} on={on} dark />
          </g>
        );
      })}

      {/* the shell itself, from the supplied vector artwork */}
      <DualSenseShell />

      {/* touchpad — clicking it is the emergency stop */}
      <g onPointerDown={fire('estop', () => onEmergencyStop?.())}
        style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}>
        <title>{`Emergency stop — click the touchpad or press ${ESTOP_HOTKEY}. Ends every active lease.`}</title>
        <path d={TOUCHPAD_PATH}
          fill={pressed === 'estop' ? 'var(--color-bad)' : 'rgba(0,0,0,.05)'}
          stroke={pressed === 'estop' ? 'var(--color-bad)' : 'rgba(0,0,0,.22)'} strokeWidth="3" />
        <text x={TOUCHPAD_MID.x} y={TOUCHPAD_MID.y} textAnchor="middle" fontSize="44"
          letterSpacing="2" fill={pressed === 'estop' ? '#2a0008' : SHELL_INK}
          fontFamily="ui-monospace, monospace" pointerEvents="none">EMERGENCY STOP</text>
        <Key x={TOUCHPAD_MID.x} y={TOUCHPAD_MID.y + 62} label={ESTOP_HOTKEY}
          on={pressed === 'estop'} />
      </g>

      {/* Light bars flanking the emergency stop. Colour is the plane's verdict;
          brightness is that plane's stick deflection, written by place(). */}
      {[['legit', 724], ['rogue', 1368]].map(([panel, x]) => {
        const lamp = lamps?.[panel] ?? 'idle';
        const base = lamp === 'idle' ? 0.22 : 0.7;
        return (
          <rect key={panel} ref={(el) => { barRefs.current[panel] = el; }}
            data-base={base} x={x} y="730" width="16" height="140" rx="8"
            pointerEvents="none" fill={TONE[lamp]} filter="url(#ds-bar-glow)"
            style={{ opacity: base, transition: 'opacity .12s linear' }} />
        );
      })}

      {/* d-pad — the valid operator's arm presets */}
      {DPAD.map((d) => {
        const on = pressed === d.preset;
        return (
          <g key={d.preset} onPointerDown={fire(d.preset, () => onArmPreset?.('legit', d.preset))}
            style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}>
            <title>{`Arm ${d.preset} for the valid operator — d-pad or key ${d.hotkey}`}</title>
            <rect x={d.cx - DPAD_HIT} y={d.cy - DPAD_HIT} width={DPAD_HIT * 2} height={DPAD_HIT * 2}
              rx="18" fill={on ? 'var(--color-ok)' : 'transparent'} opacity={on ? 0.9 : 1} />
            <Glyph kind={d.glyph} cx={d.cx} cy={d.cy} r={22} colour={on ? '#04231a' : GLYPH} />
          </g>
        );
      })}

      {/* face buttons — the hacker's arm presets */}
      {FACES.map((f) => {
        const on = pressed === `f-${f.preset}`;
        return (
          <g key={f.preset} onPointerDown={fire(`f-${f.preset}`, () => onArmPreset?.('rogue', f.preset))}
            style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}>
            <title>{`Arm ${f.preset} for the hacker — ${f.glyph} or key ${f.hotkey}`}</title>
            <circle cx={f.cx} cy={f.cy} r={FACE_R}
              fill={on ? 'var(--color-bad)' : 'transparent'} opacity={on ? 0.9 : 1} />
            <Glyph kind={f.glyph} cx={f.cx} cy={f.cy} r={26} colour={on ? '#2a0010' : GLYPH} />
          </g>
        );
      })}

      {/* preset legends, in the clear shell either side of the stick bay */}
      {DPAD.map((d, i) => (
        <g key={`ld-${d.preset}`} pointerEvents="none">
          <Glyph kind={d.glyph} cx={LEGEND_LEFT} cy={LEGEND_Y[i] - 11} r={12} colour="#fff" />
          <text x={LEGEND_LEFT + 30} y={LEGEND_Y[i]} fontSize="34" fill="#fff"
            fontFamily="ui-monospace, monospace">
            {d.preset.toUpperCase()} {d.hotkey}
          </text>
        </g>
      ))}
      {FACES.map((f, i) => (
        <g key={`lf-${f.preset}`} pointerEvents="none">
          <Glyph kind={f.glyph} cx={LEGEND_RIGHT} cy={LEGEND_Y[i] - 11} r={12} colour="#fff" />
          <text x={LEGEND_RIGHT - 30} y={LEGEND_Y[i]} textAnchor="end" fontSize="34" fill="#fff"
            fontFamily="ui-monospace, monospace">
            {f.preset.toUpperCase()} {f.hotkey}
          </text>
        </g>
      ))}

      <Stick panel="legit" />
      <Stick panel="rogue" />

      {/* plane labels, inside the stick bay under each stick */}
      <text x={STICKS.legit.cx} y="1252" textAnchor="middle" fontSize="42"
        fill={activePanel === 'legit' ? 'var(--color-ok)' : '#fff'}
        fontFamily="ui-monospace, monospace" letterSpacing="2">OPERATOR</text>
      <text x={STICKS.rogue.cx} y="1252" textAnchor="middle" fontSize="42"
        fill={activePanel === 'rogue' ? 'var(--color-bad)' : '#fff'}
        fontFamily="ui-monospace, monospace" letterSpacing="2">HACKER</text>

      <text x="1054" y="1650" textAnchor="middle" fontSize="36"
        fill={armed ? 'var(--color-info)' : 'var(--color-faint)'}
        fontFamily="ui-monospace, monospace">
        left half → operator · right half → hacker
      </text>
    </svg>
  );
}
