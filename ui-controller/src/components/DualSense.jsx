import { useCallback, useEffect, useRef, useState } from 'react';

/* A DualSense, drawn to scale in SVG and wired as a real control surface.
 *
 * The two thumbsticks are the two control planes:
 *   left  stick -> valid operator      right stick -> hacker
 *
 * All three input routes converge here. Pointer drag is handled locally;
 * keyboard and gamepad arrive through `stickRef`, which the controller reads on
 * its own animation frame so 60 Hz of stick motion never re-renders React.
 *
 * The light bars either side of the touchpad carry each plane's live verdict —
 * the same information as the lamps, in the place a PS5 actually shows state.
 */

const VB = { w: 360, h: 244 };
const TRAVEL = 13;          // px of thumb travel inside the stick well, in viewBox units
const STICKS = {
  legit: { cx: 116, cy: 150 },
  rogue: { cx: 244, cy: 150 },
};

const TONE = {
  idle:  'var(--color-faint)',
  allow: 'var(--color-ok)',
  hold:  'var(--color-warn)',
  block: 'var(--color-bad)',
};

/* Preset and action names mirror the sets backend/teleop.py validates against.
 * D-pad geometry doubles as the hit target, so the button you press is the
 * button you see. */
const DPAD = [
  { preset: 'reach',   x: 68, y: 72,  w: 16, h: 15, label: 'REACH',   hotkey: '1',
    lx: 76, ly: 68,  anchor: 'middle' },
  { preset: 'stow',    x: 68, y: 101, w: 16, h: 15, label: 'STOW',    hotkey: '2',
    lx: 76, ly: 124, anchor: 'middle' },
  { preset: 'carry',   x: 54, y: 86,  w: 15, h: 16, label: 'CARRY',   hotkey: '3',
    lx: 51, ly: 97,  anchor: 'end' },
  { preset: 'inspect', x: 83, y: 86,  w: 15, h: 16, label: 'INSPECT', hotkey: '4',
    lx: 101, ly: 97, anchor: 'start' },
];

/* Four shoulders, split by plane exactly as the thumbsticks are: the left pair
 * is the valid operator's gripper, the right pair is the hacker's. */
const SHOULDERS = [
  { key: 'l2', x: 40, y: 1, action: 'close', panel: 'legit', label: 'L2 · CLOSE', hotkey: 'E' },
  { key: 'l1', x: 40, y: 17, action: 'open', panel: 'legit', label: 'L1 · OPEN', hotkey: 'Q' },
  { key: 'r2', x: 254, y: 1, action: 'close', panel: 'rogue', label: 'R2 · CLOSE', hotkey: 'P' },
  { key: 'r1', x: 254, y: 17, action: 'open', panel: 'rogue', label: 'R1 · OPEN', hotkey: 'O' },
];

const PLANE_TONE = { legit: 'var(--color-ok)', rogue: 'var(--color-bad)' };

const ESTOP_HOTKEY = 'SPACE';

/* A keycap drawn on the pad, so every button says which key does the same
 * thing. Purely a label: the hit target is always the button underneath. */
function Key({ x, y, label, on }) {
  const w = label.length * 4.3 + 6;
  return (
    <g pointerEvents="none">
      <rect x={x - w / 2} y={y - 5.5} width={w} height="11" rx="2.5"
        fill={on ? 'var(--color-info)' : '#0d1420'}
        stroke={on ? 'var(--color-info)' : 'rgba(255,255,255,.22)'} strokeWidth="0.7" />
      <text x={x} y={y + 2.6} textAnchor="middle" fontSize="6"
        fill={on ? '#04122e' : 'var(--color-dim)'} fontFamily="ui-monospace, monospace">
        {label}
      </text>
    </g>
  );
}

export default function DualSense({
  stickRef, onStick, lamps, leases, driving, disabled,
  onArmPreset, onGripper, onEmergencyStop,
}) {
  const svgRef = useRef(null);
  const thumbRefs = useRef({});
  const glowRefs = useRef({});
  const dragging = useRef(null);
  const [activePanel, setActivePanel] = useState(null);
  const [pressed, setPressed] = useState(null);

  /* Arm presets ride whichever plane holds a lease (or is actively driving).
   * With no lease yet, ensureLease() takes a short aux lease so the press still
   * produces a real identity/policy verdict rather than an inert button.
   * Gripper shoulders are plane-addressed (left = operator, right = hacker). */
  const target = (leases?.legit && 'legit') || (leases?.rogue && 'rogue')
    || (driving?.legit && 'legit') || (driving?.rogue && 'rogue')
    || activePanel || 'legit';
  const armed = Boolean(leases?.legit || leases?.rogue);

  const fire = (key, run) => (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    if (disabled) return;
    setPressed(key);
    setTimeout(() => setPressed((k) => (k === key ? null : k)), 180);
    run();
  };

  const place = useCallback((panel, vec) => {
    const t = thumbRefs.current[panel];
    const g = glowRefs.current[panel];
    if (t) t.setAttribute('transform', `translate(${vec.x * TRAVEL} ${-vec.y * TRAVEL})`);
    if (g) g.style.opacity = Math.min(1, Math.hypot(vec.x, vec.y)) > 0.12 ? '1' : '0';
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
    return { x: (ev.clientX - rect.left) * scale, y: (ev.clientY - rect.top) * scale };
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

  const Stick = ({ panel }) => {
    const { cx, cy } = STICKS[panel];
    const colour = TONE[lamps?.[panel] ?? 'idle'];
    return (
      <g onPointerDown={grab(panel)} onPointerMove={move} onPointerUp={release}
        onPointerCancel={release} style={{ cursor: disabled ? 'not-allowed' : 'grab' }}>
        {/* well */}
        <circle cx={cx} cy={cy} r="27" fill="#0a0e17" stroke="rgba(255,255,255,.09)" />
        <circle cx={cx} cy={cy} r="21" fill="#070a11" />
        <g ref={(el) => { glowRefs.current[panel] = el; }} style={{ opacity: 0, transition: 'opacity .15s' }}>
          <circle cx={cx} cy={cy} r="27" fill="none" stroke={colour} strokeWidth="1.5" opacity=".85" />
          <circle cx={cx} cy={cy} r="31" fill="none" stroke={colour} strokeWidth="1" opacity=".28" />
        </g>
        <g ref={(el) => { thumbRefs.current[panel] = el; }} style={{ transition: 'transform .08s linear' }}>
          <circle cx={cx} cy={cy} r="18" fill={`url(#thumb-${panel})`} stroke="rgba(0,0,0,.55)" />
          <ellipse cx={cx} cy={cy - 3} rx="12" ry="9" fill="rgba(255,255,255,.05)" />
          <circle cx={cx} cy={cy} r="11" fill="none" stroke="rgba(0,0,0,.35)" strokeWidth="3" />
        </g>
      </g>
    );
  };

  return (
    <svg ref={svgRef} viewBox={`0 0 ${VB.w} ${VB.h}`} className="block h-auto w-full select-none"
      role="group" aria-label="DualSense controller: left stick drives the valid operator, right stick drives the hacker">
      <defs>
        <linearGradient id="ds-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2b3446" />
          <stop offset="45%" stopColor="#1b2231" />
          <stop offset="100%" stopColor="#0e131d" />
        </linearGradient>
        <linearGradient id="ds-plate" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#39445a" />
          <stop offset="100%" stopColor="#232c3d" />
        </linearGradient>
        {Object.keys(STICKS).map((p) => (
          <radialGradient key={p} id={`thumb-${p}`} cx="38%" cy="30%">
            <stop offset="0%" stopColor="#5d6b8c" />
            <stop offset="100%" stopColor="#1d2534" />
          </radialGradient>
        ))}
        <filter id="ds-shadow" x="-30%" y="-30%" width="160%" height="170%">
          <feDropShadow dx="0" dy="10" stdDeviation="12" floodColor="#000" floodOpacity=".65" />
        </filter>
      </defs>

      {/* shoulders — gripper, left pair operator, right pair hacker */}
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
            <rect x={b.x} y={b.y} width="66" height="15" rx="6"
              fill={on ? tone : '#222b3c'} stroke={tone} strokeWidth="0.6" strokeOpacity=".5" />
            <text x={b.x + 24} y={b.y + 10.5} textAnchor="middle" fontSize="6.6"
              fill={on ? '#04122e' : tone} fontFamily="ui-monospace, monospace"
              pointerEvents="none">{b.label}</text>
            <Key x={b.x + 54} y={b.y + 7.5} label={b.hotkey} on={on} />
          </g>
        );
      })}

      {/* body */}
      <path filter="url(#ds-shadow)" fill="url(#ds-body)" stroke="rgba(255,255,255,.09)"
        d="M 100 30 L 260 30 C 298 30 340 50 348 96 C 354 128 344 154 330 172
           C 320 186 316 208 306 222 C 296 236 274 236 262 224 C 244 206 224 196 204 194
           L 156 194 C 136 196 116 206 98 224 C 86 236 64 236 54 222
           C 44 208 40 186 30 172 C 16 154 6 128 12 96 C 20 50 62 30 100 30 Z" />

      {/* touchpad + light bars (each bar is one control plane's verdict) */}
      <rect x="139" y="50" width="82" height="46" rx="9" fill="url(#ds-plate)"
        stroke="rgba(255,255,255,.10)" />
      {[['legit', 130], ['rogue', 225]].map(([panel, x]) => {
        const colour = TONE[lamps?.[panel] ?? 'idle'];
        const on = (lamps?.[panel] ?? 'idle') !== 'idle';
        return (
          <rect key={panel} x={x} y="53" width="5" height="40" rx="2.5" fill={colour}
            className={on ? 'a-breathe' : ''} opacity={on ? 1 : 0.25}
            style={on ? { filter: `drop-shadow(0 0 6px ${colour})` } : undefined} />
        );
      })}

      {/* d-pad — one arm preset per direction */}
      <g>
        {DPAD.map((d) => (
          <g key={d.preset} onPointerDown={fire(d.preset, () => onArmPreset?.(target, d.preset))}
            style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}>
            <title>{`Arm ${d.preset} — d-pad or key ${d.hotkey}`}</title>
            <rect x={d.x} y={d.y} width={d.w} height={d.h} rx="3.5"
              fill={pressed === d.preset ? 'var(--color-info)' : '#2a3346'}
              stroke="rgba(0,0,0,.45)" />
            <text x={d.x + d.w / 2} y={d.y + d.h / 2 + 2.4} textAnchor="middle" fontSize="7"
              fill={pressed === d.preset ? '#04122e' : 'var(--color-dim)'}
              fontFamily="ui-monospace, monospace" pointerEvents="none">{d.hotkey}</text>
          </g>
        ))}
        <rect x="70" y="88" width="12" height="12" rx="2" fill="#1b2231" pointerEvents="none" />
        {DPAD.map((d) => (
          <text key={d.preset} x={d.lx} y={d.ly} textAnchor={d.anchor} fontSize="4.6"
            fill="var(--color-faint)" fontFamily="ui-monospace, monospace"
            pointerEvents="none">{d.label}</text>
        ))}
      </g>
      <text x="76" y="136" textAnchor="middle" fontSize="6" fill="var(--color-faint)"
        fontFamily="ui-monospace, monospace">ARM</text>

      {/* face buttons */}
      <g stroke="rgba(0,0,0,.4)">
        <circle cx="276" cy="76" r="10" fill="#2a3346" />
        <circle cx="298" cy="94" r="10" fill="#2a3346" />
        <circle cx="276" cy="112" r="10" fill="#2a3346" />
        <circle cx="254" cy="94" r="10" fill="#2a3346" />
      </g>
      {/* Circle is the emergency stop, on screen and on the physical pad. */}
      <g onPointerDown={fire('estop', () => onEmergencyStop?.())}
        style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}>
        <title>{`Emergency stop — Circle or ${ESTOP_HOTKEY}. Ends every active lease.`}</title>
        <circle cx="298" cy="94" r="11" fill={pressed === 'estop' ? 'var(--color-bad)' : 'transparent'} />
        <circle cx="298" cy="94" r="5.5" fill="none" stroke="var(--color-bad)" strokeWidth="1.6" />
      </g>
      <text x="298" y="118" textAnchor="middle" fontSize="7" fill="var(--color-bad)"
        fontFamily="ui-monospace, monospace">STOP</text>
      <Key x="298" y="130" label={ESTOP_HOTKEY} on={pressed === 'estop'} />

      <Stick panel="legit" />
      <Stick panel="rogue" />

      {/* PS button + speaker grille */}
      <circle cx="180" cy="150" r="7" fill="#1a2231" stroke="rgba(255,255,255,.12)" />
      <g fill="rgba(255,255,255,.10)">
        {[0, 1, 2].map((i) => <circle key={i} cx={172 + i * 8} cy={176} r="1.6" />)}
      </g>

      <text x={STICKS.legit.cx} y="196" textAnchor="middle" fontSize="8.5"
        fill={activePanel === 'legit' ? 'var(--color-ok)' : 'var(--color-faint)'}
        fontFamily="ui-monospace, monospace" letterSpacing="0.5">OPERATOR</text>
      <text x={STICKS.rogue.cx} y="196" textAnchor="middle" fontSize="8.5"
        fill={activePanel === 'rogue' ? 'var(--color-bad)' : 'var(--color-faint)'}
        fontFamily="ui-monospace, monospace" letterSpacing="0.5">HACKER</text>

      <text x="180" y="212" textAnchor="middle" fontSize="7"
        fill={armed ? 'var(--color-info)' : 'var(--color-faint)'}
        fontFamily="ui-monospace, monospace">
        {`arm → ${target === 'legit' ? 'operator' : 'hacker'} · gripper → per shoulder`}
      </text>
    </svg>
  );
}
