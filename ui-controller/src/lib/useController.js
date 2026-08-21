import { useCallback, useEffect, useRef, useState } from 'react';
import {
  DEADZONE, FLOOR, LOOKAHEAD, POLICY_MAX_SPEED, TICK_MS,
  authorize, bridgeReachable, clamp, driveHome, getEvents, getHealth,
  getState, getTimeline, resetBackend, sendMove, sendStop, speedFor, zoneAt,
} from './omniguard.js';

const PANEL_IDS = ['legit', 'rogue'];
const blankStick = () => ({ vec: { x: 0, y: 0 }, mag: 0 });
const blankRuntime = () => ({ authSig: null, authAt: 0, inflight: false, streaming: false, padActive: false });
const blankView = () => ({ lamp: 'idle', lampLabel: null, speed: 0, zone: null, setpoint: null, reasons: [], log: [] });

const fromEntries = (fn) => Object.fromEntries(PANEL_IDS.map((id) => [id, fn(id)]));

let logSeq = 0;

export function useController(cfg) {
  const cfgRef = useRef(cfg);
  cfgRef.current = cfg;

  const sticks = useRef(fromEntries(blankStick));
  const runtime = useRef(fromEntries(blankRuntime));
  const robot = useRef({ x: 0, y: 0 });
  const trail = useRef([]);

  const [options, setOptions] = useState({ overspeed: false, bypass: false });
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const [view, setView] = useState(() => fromEntries(blankView));
  const viewRef = useRef(view);
  viewRef.current = view;

  const [world, setWorld] = useState({ robot: { x: 0, y: 0 }, trail: [], setpoints: [] });
  const [status, setStatus] = useState({ bridge: false });
  const [events, setEvents] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [health, setHealth] = useState(null);
  const [padLabel, setPadLabel] = useState('Gamepad: checking…');
  const [external, setExternal] = useState({ legit: null, rogue: null });
  const [resetting, setResetting] = useState(false);

  const patch = useCallback((id, next) => {
    setView((prev) => ({ ...prev, [id]: { ...prev[id], ...next } }));
  }, []);

  const pushLog = useCallback((id, decision, detail) => {
    setView((prev) => {
      const log = [{ id: ++logSeq, time: new Date().toLocaleTimeString([], { hour12: false }), decision, detail },
        ...prev[id].log].slice(0, 40);
      return { ...prev, [id]: { ...prev[id], log } };
    });
  }, []);

  const setStick = useCallback((id, next) => { sticks.current[id] = next; }, []);

  /* ----------------------------------------------------------- verdicts */
  const applyVerdict = useCallback((id, res) => {
    const rt = runtime.current[id];
    if (res.final_decision === 'ALLOW') {
      patch(id, { lamp: 'allow', lampLabel: null, reasons: [res.policy_decision, `risk ${res.anomaly_risk_score}`] });
      pushLog(id, 'ALLOW', `${res.destination} @ ${res.speed} m/s`);
      rt.streaming = true;
      return;
    }
    rt.streaming = false;
    sendStop(cfgRef.current);
    if (res.final_decision === 'HOLD') {
      patch(id, { lamp: 'hold', lampLabel: null, reasons: res.reasons.length ? res.reasons : ['HOLD_FOR_REVIEW'] });
      pushLog(id, 'HOLD', `risk ${res.anomaly_risk_score}`);
    } else {
      patch(id, { lamp: 'block', lampLabel: null, reasons: res.reasons });
      pushLog(id, 'BLOCK', res.reasons.join(', '));
    }
  }, [patch, pushLog]);

  const requestAuth = useCallback(async (id, zone, speed) => {
    const rt = runtime.current[id];
    rt.inflight = true;
    try {
      applyVerdict(id, await authorize(cfgRef.current, id, zone, speed));
    } catch (err) {
      rt.streaming = false;
      sendStop(cfgRef.current);
      patch(id, { lamp: 'block', lampLabel: 'API DOWN', reasons: ['API_UNREACHABLE'] });
      pushLog(id, 'ERROR', String(err.message ?? err));
    } finally {
      rt.inflight = false;
    }
  }, [applyVerdict, patch, pushLog]);

  /* -------------------------------------------------------- dead reckoning
   * The bridge has no pose readback, so we integrate commanded motion.
   * Reset re-syncs to the origin. */
  const advance = useCallback((sp, speed, dt) => {
    const dx = sp.x - robot.current.x;
    const dy = sp.y - robot.current.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 0.02) return;
    const step = Math.min(dist, speed * dt);
    robot.current = { x: robot.current.x + (dx / dist) * step, y: robot.current.y + (dy / dist) * step };
    trail.current = [...trail.current.slice(-399), robot.current];
  }, []);

  /* ------------------------------------------------------------ gamepad
   * Left stick drives the operator, right stick the attacker. Gated to secure
   * contexts by the browser, so over plain http on a bare IP this stays
   * unavailable and the on-screen sticks carry the demo. */
  const pollGamepad = useCallback(() => {
    if (!navigator.getGamepads) return;
    const pad = Array.from(navigator.getGamepads()).find(Boolean);
    if (!pad) return;
    const next = { legit: null, rogue: null };
    PANEL_IDS.forEach((id, i) => {
      const x = pad.axes[i * 2] ?? 0;
      const y = -(pad.axes[i * 2 + 1] ?? 0);
      const mag = Math.min(1, Math.hypot(x, y));
      const rt = runtime.current[id];
      if (mag > DEADZONE) {
        sticks.current[id] = { vec: { x, y }, mag };
        next[id] = { vec: { x, y }, mag };
        rt.padActive = true;
      } else if (rt.padActive) {
        // Physical stick released — do not leave the last value latched.
        sticks.current[id] = blankStick();
        rt.padActive = false;
      }
    });
    setExternal(next);
  }, []);

  /* --------------------------------------------------------------- loop */
  useEffect(() => {
    const dt = TICK_MS / 1000;

    const tick = () => {
      pollGamepad();
      const cfg = cfgRef.current;
      const opts = optionsRef.current;
      const setpoints = [];

      for (const id of PANEL_IDS) {
        const stick = sticks.current[id];
        const rt = runtime.current[id];
        const current = viewRef.current[id];

        if (stick.mag <= DEADZONE) {
          if (rt.streaming || rt.authSig) {
            rt.streaming = false;
            rt.authSig = null;
            sendStop(cfg);
            patch(id, { lamp: 'idle', lampLabel: null, reasons: [] });
          }
          if (current.speed !== 0 || current.setpoint) patch(id, { speed: 0, zone: null, setpoint: null });
          continue;
        }

        const overspeed = id === 'rogue' && opts.overspeed;
        const speed = speedFor(stick.mag, { overspeed });
        const len = Math.hypot(stick.vec.x, stick.vec.y) || 1;
        const sp = {
          x: clamp(robot.current.x + (stick.vec.x / len) * LOOKAHEAD, FLOOR[0], FLOOR[2]),
          y: clamp(robot.current.y + (stick.vec.y / len) * LOOKAHEAD, FLOOR[1], FLOOR[3]),
        };
        const zone = zoneAt(sp.x, sp.y);
        setpoints.push({ id, sp });
        patch(id, { speed, zone, setpoint: sp });

        /* An attacker whose client skips the broker entirely. The robot moves
         * and nothing stops it — the live argument for closing port 8899. */
        if (id === 'rogue' && opts.bypass) {
          if (!rt.streaming) {
            rt.streaming = true;
            patch(id, { lamp: 'block', lampLabel: 'BROKER BYPASSED', reasons: ['POLICY_ENGINE_NOT_CONSULTED'] });
            pushLog(id, 'BYPASS', 'driving :8899 directly');
          }
          sendMove(cfg, sp.x, sp.y, speed);
          advance(sp, speed, dt);
          continue;
        }

        /* Authorize on change ONLY — never on a timer.
         *
         * backend/behavior.py derives seconds_since_last_command server-side, and
         * the retrained model scores any gap <= 5s at risk 0.60, which is HOLD.
         * A timed re-auth therefore guarantees the *legitimate* operator gets
         * held on their second command and escalates to BLOCK by the fourth
         * (measured: 0.62 -> 0.73 -> 0.74 -> 0.81). One authorization per grab,
         * per zone, is the fewest commands the policy path can be asked for. */
        const sig = `${zone}|${speed > POLICY_MAX_SPEED ? 'over' : 'ok'}`;
        if (!rt.inflight && sig !== rt.authSig) {
          rt.authSig = sig;
          rt.authAt = Date.now();
          requestAuth(id, zone, speed);
        }

        if (rt.streaming) {
          sendMove(cfg, sp.x, sp.y, speed);
          advance(sp, speed, dt);
        }
      }

      setWorld({ robot: robot.current, trail: trail.current, setpoints });
    };

    const handle = setInterval(tick, TICK_MS);
    return () => clearInterval(handle);
  }, [advance, patch, pollGamepad, pushLog, requestAuth]);

  /* ------------------------------------------------------ status polling */
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      const cfg = cfgRef.current;
      let next = {};
      try {
        const s = await getState(cfg);
        next = {
          robot_status: s.robot_status, robot_zone: s.robot_zone,
          credential_status: s.credential_status, agent_status: s.agent_status,
          robot_speed: s.robot_speed, protection_enabled: s.protection_enabled,
        };
      } catch {
        next = { robot_status: 'API DOWN', robot_zone: null, credential_status: null };
      }
      next.bridge = await bridgeReachable(cfg);
      if (alive) setStatus(next);

      const [ev, tl] = await Promise.allSettled([getEvents(cfg), getTimeline(cfg)]);
      if (!alive) return;
      if (ev.status === 'fulfilled') setEvents(ev.value.slice(0, 12));
      if (tl.status === 'fulfilled') setTimeline(tl.value);
    };
    poll();
    const handle = setInterval(poll, 1500);
    return () => { alive = false; clearInterval(handle); };
  }, [cfg.api, cfg.bridge]);

  /* Model provenance is fetched once — it does not change while running, and it
   * is what lets the UI state plainly that the model does not drive the robot. */
  useEffect(() => {
    let alive = true;
    getHealth(cfgRef.current)
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setHealth(null));
    return () => { alive = false; };
  }, [cfg.api]);

  /* ----------------------------------------------------------- gamepad ui */
  useEffect(() => {
    const refresh = () => {
      if (!navigator.getGamepads) {
        setPadLabel('Gamepad: needs https or 127.0.0.1');
        return;
      }
      const pad = Array.from(navigator.getGamepads()).find(Boolean);
      setPadLabel(pad ? `Gamepad: ${pad.id.slice(0, 32)}` : 'Gamepad: none connected');
    };
    refresh();
    window.addEventListener('gamepadconnected', refresh);
    window.addEventListener('gamepaddisconnected', refresh);
    return () => {
      window.removeEventListener('gamepadconnected', refresh);
      window.removeEventListener('gamepaddisconnected', refresh);
    };
  }, []);

  /* ------------------------------------------------------------- deadman
   * Releasing the stick is not the only way to stop. Losing the tab or the
   * network must also stop the robot. */
  useEffect(() => {
    const halt = () => {
      for (const id of PANEL_IDS) {
        sticks.current[id] = blankStick();
        runtime.current[id] = blankRuntime();
      }
      sendStop(cfgRef.current);
    };
    const onVisibility = () => { if (document.hidden) halt(); };
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('blur', halt);
    window.addEventListener('pagehide', halt);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('blur', halt);
      window.removeEventListener('pagehide', halt);
    };
  }, []);

  /* --------------------------------------------------------------- reset */
  const reset = useCallback(async () => {
    setResetting(true);
    const cfg = cfgRef.current;
    for (const id of PANEL_IDS) {
      sticks.current[id] = blankStick();
      runtime.current[id] = blankRuntime();
    }
    setOptions({ overspeed: false, bypass: false });
    setView(fromEntries(blankView));
    sendStop(cfg);
    try {
      await resetBackend(cfg);
      await driveHome(cfg);
    } catch { /* surfaced by the status poll */ }
    robot.current = { x: 0, y: 0 };
    trail.current = [];
    setWorld({ robot: robot.current, trail: [], setpoints: [] });
    setEvents([]);
    setTimeline([]);
    setResetting(false);
  }, []);

  return {
    view, world, status, events, timeline, health,
    options, setOptions, setStick, external, padLabel, reset, resetting,
  };
}
