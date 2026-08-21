import { useCallback, useEffect, useRef, useState } from 'react';

const RADIUS = 64; // px of travel from centre
const KEY_VECTORS = {
  ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0],
  w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0],
};

/**
 * Analog stick. Springs back to centre on release.
 *
 * Three input routes, because a pointer-only control is unusable by keyboard:
 *   pointer   — drag anywhere on the pad
 *   keyboard  — arrows or WASD while focused, held keys combine diagonally
 *   gamepad   — `external`, which only takes over while the pointer is idle
 */
export default function Joystick({ tone, onChange, external, label }) {
  const padRef = useRef(null);
  const pointerId = useRef(null);
  const heldKeys = useRef(new Set());
  const [thumb, setThumb] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [keying, setKeying] = useState(false);

  const emit = useCallback((dx, dy) => {
    const mag = Math.min(1, Math.hypot(dx, dy) / RADIUS);
    // Screen y grows downward, world y grows up.
    onChange({ vec: { x: dx / RADIUS, y: -dy / RADIUS }, mag });
  }, [onChange]);

  const centre = useCallback(() => {
    setThumb({ x: 0, y: 0 });
    onChange({ vec: { x: 0, y: 0 }, mag: 0 });
  }, [onChange]);

  /* ------------------------------------------------------------- pointer */
  const track = useCallback((ev) => {
    const box = padRef.current?.getBoundingClientRect();
    if (!box) return;
    let dx = ev.clientX - (box.left + box.width / 2);
    let dy = ev.clientY - (box.top + box.height / 2);
    const dist = Math.hypot(dx, dy);
    if (dist > RADIUS) { dx = (dx / dist) * RADIUS; dy = (dy / dist) * RADIUS; }
    setThumb({ x: dx, y: dy });
    emit(dx, dy);
  }, [emit]);

  const release = useCallback((ev) => {
    if (pointerId.current !== ev.pointerId) return;
    pointerId.current = null;
    setDragging(false);
    centre();
  }, [centre]);

  const grab = (ev) => {
    pointerId.current = ev.pointerId;
    setDragging(true);
    ev.currentTarget.setPointerCapture(ev.pointerId);
    track(ev);
  };

  /* ------------------------------------------------------------ keyboard */
  const applyKeys = useCallback(() => {
    let x = 0, y = 0;
    for (const k of heldKeys.current) {
      const v = KEY_VECTORS[k];
      if (v) { x += v[0]; y += v[1]; }
    }
    if (!x && !y) { setKeying(false); centre(); return; }
    const len = Math.hypot(x, y);
    const dx = (x / len) * RADIUS, dy = (y / len) * RADIUS;
    setKeying(true);
    setThumb({ x: dx, y: dy });
    emit(dx, dy);
  }, [centre, emit]);

  const onKeyDown = (ev) => {
    const key = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
    if (!KEY_VECTORS[key]) return;
    ev.preventDefault();           // stop arrows scrolling the page
    heldKeys.current.add(key);
    applyKeys();
  };
  const onKeyUp = (ev) => {
    const key = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
    if (!KEY_VECTORS[key]) return;
    heldKeys.current.delete(key);
    applyKeys();
  };
  const onBlur = () => {
    if (heldKeys.current.size) { heldKeys.current.clear(); applyKeys(); }
  };

  /* A gamepad owns the stick only while pointer and keyboard are idle. */
  useEffect(() => {
    if (dragging || keying || !external) return;
    setThumb({ x: external.vec.x * RADIUS, y: -external.vec.y * RADIUS });
  }, [dragging, keying, external]);

  const live = Math.hypot(thumb.x, thumb.y) > 6;
  const accent = tone === 'ok' ? 'var(--color-ok)' : 'var(--color-bad)';

  return (
    <div
      ref={padRef}
      role="application"
      aria-label={label}
      tabIndex={0}
      onPointerDown={grab}
      onPointerMove={(e) => pointerId.current === e.pointerId && track(e)}
      onPointerUp={release}
      onPointerCancel={release}
      onKeyDown={onKeyDown}
      onKeyUp={onKeyUp}
      onBlur={onBlur}
      className={`relative size-[196px] shrink-0 touch-none select-none rounded-full border
                  transition-shadow duration-200
                  ${live ? 'border-line-hi' : 'border-line'}
                  ${dragging ? 'cursor-grabbing' : 'cursor-grab'}`}
      style={{
        background: 'radial-gradient(circle at 50% 28%, #27324a 0%, #0c1220 76%)',
        boxShadow: `inset 0 10px 32px rgba(0,0,0,.75)${live ? `, 0 0 52px -10px ${accent}` : ''}`,
      }}
    >
      {/* travel ring */}
      <div className="pointer-events-none absolute inset-[14px] rounded-full border border-dashed border-line" />
      {/* crosshair */}
      <div className="pointer-events-none absolute inset-0 opacity-80" style={{
        background:
          'linear-gradient(rgba(255,255,255,.07),rgba(255,255,255,.07)) 50% 50%/1px 58% no-repeat,' +
          'linear-gradient(rgba(255,255,255,.07),rgba(255,255,255,.07)) 50% 50%/58% 1px no-repeat',
      }} />
      {/* live ping */}
      {live && (
        <span className="a-ping pointer-events-none absolute left-1/2 top-1/2 size-16 -translate-x-1/2 -translate-y-1/2
                         rounded-full border" style={{ borderColor: accent }} />
      )}
      {/* thumb */}
      <div
        className={`pointer-events-none absolute left-1/2 top-1/2 size-[76px] rounded-full border
                    ${dragging ? '' : 'transition-transform duration-150 ease-out'}`}
        style={{
          transform: `translate(calc(-50% + ${thumb.x}px), calc(-50% + ${thumb.y}px))`,
          background: 'radial-gradient(circle at 38% 28%, #6b7ca4 0%, #232d44 74%)',
          borderColor: live ? accent : '#3c4864',
          boxShadow: live
            ? `0 8px 24px rgba(0,0,0,.6), inset 0 2px 6px rgba(255,255,255,.18), 0 0 22px -4px ${accent}`
            : '0 8px 24px rgba(0,0,0,.6), inset 0 2px 6px rgba(255,255,255,.18)',
        }}
      />
      <span className="pointer-events-none absolute inset-x-0 -bottom-6 text-center text-[10px] text-faint">
        drag · arrows · WASD
      </span>
    </div>
  );
}
