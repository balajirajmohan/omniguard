import { useEffect, useRef, useState } from 'react';

/* Keyboard driving, without click-to-focus.
 *
 * The old build put the key handler on the joystick element, so the pad had to
 * be clicked before WASD did anything — discoverable only by accident. The
 * listener now lives on window and splits the keys across the two control
 * planes, mirroring the two thumbsticks:
 *
 *   W A S D      -> valid operator   (left stick)
 *   arrow keys   -> hacker           (right stick)
 *
 * Nothing needs focus, and the two planes can be driven at the same time.
 */
export const BINDINGS = {
  legit: { w: [0, 1], a: [-1, 0], s: [0, -1], d: [1, 0] },
  rogue: { ArrowUp: [0, 1], ArrowLeft: [-1, 0], ArrowDown: [0, -1], ArrowRight: [1, 0] },
};

/* Arm, gripper and emergency stop, on the keyboard.
 *
 * Arm presets ride whichever plane holds a lease — there is one d-pad, so there
 * is one arm control. The gripper is split per plane, like the shoulders it
 * mirrors. `pad` names the button each key matches, so the on-screen controller
 * and this table cannot drift apart without a test failing.
 *
 * Preset and action names match the sets backend/teleop.py validates against. */
export const AUX_KEYS = {
  1: { kind: 'arm', value: 'reach', pad: 'dpad-up' },
  2: { kind: 'arm', value: 'stow', pad: 'dpad-down' },
  3: { kind: 'arm', value: 'carry', pad: 'dpad-left' },
  4: { kind: 'arm', value: 'inspect', pad: 'dpad-right' },
  /* Gripper keys are per plane, matching the shoulders: the operator's sit by
   * WASD, the hacker's by the arrow keys. */
  q: { kind: 'gripper', value: 'open', panel: 'legit', pad: 'L1' },
  e: { kind: 'gripper', value: 'close', panel: 'legit', pad: 'L2' },
  o: { kind: 'gripper', value: 'open', panel: 'rogue', pad: 'R1' },
  p: { kind: 'gripper', value: 'close', panel: 'rogue', pad: 'R2' },
  ' ': { kind: 'estop', value: null, pad: 'circle' },
};

const normalise = (ev) => (ev.key.length === 1 ? ev.key.toLowerCase() : ev.key);

/** Pure: held keys -> a stick vector for one plane. Extracted so the mapping is
 *  testable without a DOM. Diagonals are normalised so they are not faster. */
export function vectorFor(held, panel) {
  const map = BINDINGS[panel] ?? {};
  let x = 0;
  let y = 0;
  for (const key of held) {
    const v = map[key];
    if (v) { x += v[0]; y += v[1]; }
  }
  if (x === 0 && y === 0) return { vec: { x: 0, y: 0 }, mag: 0 };
  const len = Math.hypot(x, y);
  return { vec: { x: x / len, y: y / len }, mag: 1 };
}

/** True while the user is typing, so Settings inputs keep working normally. */
function isTyping(target) {
  if (!target) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

export function useKeyboardControl(setStick, { enabled = true, actions } = {}) {
  const held = useRef(new Set());
  const [active, setActive] = useState({ legit: false, rogue: false });
  /* Held in a ref so a new actions object every render does not re-subscribe
   * the window listeners mid-keypress. */
  const actionsRef = useRef(actions);
  actionsRef.current = actions;

  useEffect(() => {
    if (!enabled) return undefined;

    const apply = () => {
      const next = { legit: false, rogue: false };
      for (const panel of Object.keys(BINDINGS)) {
        const stick = vectorFor(held.current, panel);
        setStick(panel, stick);
        next[panel] = stick.mag > 0;
      }
      setActive((prev) =>
        prev.legit === next.legit && prev.rogue === next.rogue ? prev : next);
    };

    const isBound = (key) => key in BINDINGS.legit || key in BINDINGS.rogue;

    const onDown = (ev) => {
      if (ev.repeat || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      if (isTyping(ev.target)) return;
      const key = normalise(ev);

      /* One command per physical press: ev.repeat is already rejected above, so
       * holding the key does not stream duplicates at the OS repeat rate. */
      const aux = AUX_KEYS[key];
      if (aux) {
        ev.preventDefault();        // space must not scroll or re-fire a button
        const a = actionsRef.current;
        if (aux.kind === 'arm') a?.armPreset?.(aux.value);
        else if (aux.kind === 'gripper') a?.gripperFor?.(aux.panel, aux.value);
        else a?.emergencyStop?.();
        return;
      }

      if (!isBound(key)) return;
      ev.preventDefault();          // arrows must not scroll the page
      held.current.add(key);
      apply();
    };

    const onUp = (ev) => {
      const key = normalise(ev);
      if (!isBound(key)) return;
      held.current.delete(key);
      apply();
    };

    /* Losing the window with a key down would otherwise latch that direction. */
    const release = () => {
      if (!held.current.size) return;
      held.current.clear();
      apply();
    };

    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);
    window.addEventListener('blur', release);
    document.addEventListener('visibilitychange', release);
    return () => {
      window.removeEventListener('keydown', onDown);
      window.removeEventListener('keyup', onUp);
      window.removeEventListener('blur', release);
      document.removeEventListener('visibilitychange', release);
      release();
    };
  }, [enabled, setStick]);

  return active;
}
