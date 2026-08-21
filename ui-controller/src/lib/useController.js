import { useCallback, useEffect, useRef, useState } from 'react';
import {
  DEADZONE, FALLBACK_TELEOP_CONFIG, LOOKAHEAD,
  clamp, getEvents, getHealth, getState, getTeleopConfig, getTimeline,
  readPosition, rejectionReasons, resetBackend, speedFor, teleopMove, teleopStart,
  teleopStop, zoneAt,
} from './omniguard.js';

const PANEL_IDS = ['legit', 'rogue'];
const IDLE_POLL_MS = 1500;
const ACTIVE_POLL_MS = 350;

const blankStick = () => ({ vec: { x: 0, y: 0 }, mag: 0 });
const blankSession = () => ({
  phase: 'idle',        // idle | starting | streaming | denied
  controlId: null,
  expiresAt: 0,
  maxSpeed: null,
  allowedZones: null,
  sequence: 0,
  inflight: false,
  padActive: false,
});
const blankView = () => ({
  lamp: 'idle', lampLabel: null, speed: 0, zone: null, setpoint: null,
  reasons: [], log: [], lease: null, ai: null,
});

const fromEntries = (fn) => Object.fromEntries(PANEL_IDS.map((id) => [id, fn(id)]));
let logSeq = 0;

export function useController(cfg) {
  const cfgRef = useRef(cfg);
  cfgRef.current = cfg;

  const sticks = useRef(fromEntries(blankStick));
  const sessions = useRef(fromEntries(blankSession));

  const [teleopConfig, setTeleopConfig] = useState(FALLBACK_TELEOP_CONFIG);
  const [gatewayReady, setGatewayReady] = useState(null); // null = unknown
  const teleopRef = useRef(FALLBACK_TELEOP_CONFIG);
  teleopRef.current = teleopConfig;

  const [options, setOptions] = useState({ overspeed: false });
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const [view, setView] = useState(() => fromEntries(blankView));
  const [world, setWorld] = useState({ robot: null, target: null, setpoints: [], trail: [] });
  const [status, setStatus] = useState({});
  const [events, setEvents] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [health, setHealth] = useState(null);
  const [padLabel, setPadLabel] = useState('Gamepad: checking…');
  const [external, setExternal] = useState({ legit: null, rogue: null });
  const [resetting, setResetting] = useState(false);

  /* Physical pose, from the backend only. Never estimated — a map that invents
   * a position makes every zone read-out a guess. */
  const robotRef = useRef(null);
  const trailRef = useRef([]);

  const patch = useCallback((id, next) => {
    setView((prev) => ({ ...prev, [id]: { ...prev[id], ...next } }));
  }, []);

  const pushLog = useCallback((id, decision, detail) => {
    setView((prev) => {
      const log = [{
        id: ++logSeq,
        time: new Date().toLocaleTimeString([], { hour12: false }),
        decision, detail,
      }, ...prev[id].log].slice(0, 40);
      return { ...prev, [id]: { ...prev[id], log } };
    });
  }, []);

  const setStick = useCallback((id, next) => { sticks.current[id] = next; }, []);

  /* --------------------------------------------------------------- config */
  useEffect(() => {
    let alive = true;
    getTeleopConfig(cfgRef.current)
      .then((c) => { if (alive) { setTeleopConfig(c); setGatewayReady(true); } })
      .catch(() => { if (alive) { setTeleopConfig(FALLBACK_TELEOP_CONFIG); setGatewayReady(false); } });
    return () => { alive = false; };
  }, [cfg.api]);

  /* ---------------------------------------------------------------- stop */
  const stopSession = useCallback(async (id, reason) => {
    const s = sessions.current[id];
    const controlId = s.controlId;
    sessions.current[id] = blankSession();
    patch(id, { lamp: 'idle', lampLabel: null, reasons: [], lease: null, speed: 0, zone: null, setpoint: null });
    if (!controlId) return;
    try {
      await teleopStop(cfgRef.current, { controlId, reason });
    } catch {
      /* The backend deadman is the real guarantee; a failed stop call must not
       * throw into the loop. */
    }
  }, [patch]);

  /* --------------------------------------------------------------- start */
  const startSession = useCallback(async (id, point, speed) => {
    const s = sessions.current[id];
    s.phase = 'starting';
    s.inflight = true;
    patch(id, { lamp: 'idle', lampLabel: 'AUTHORIZING' });
    try {
      const res = await teleopStart(cfgRef.current, id, { ...point, speed });
      const ai = res.ai ?? null;
      if (res.final_decision === 'ALLOW' && res.control_id) {
        sessions.current[id] = {
          ...blankSession(),
          phase: 'streaming',
          controlId: res.control_id,
          expiresAt: res.expires_at ? Date.parse(res.expires_at) : Date.now() + 30_000,
          maxSpeed: res.max_speed ?? null,
          allowedZones: res.allowed_zones ?? null,
          sequence: 0,
        };
        patch(id, {
          lamp: 'allow', lampLabel: 'LEASE ACTIVE', reasons: [res.policy_decision].filter(Boolean),
          lease: {
            controlId: res.control_id, expiresAt: res.expires_at,
            maxSpeed: res.max_speed, allowedZones: res.allowed_zones,
          },
          ai,
        });
        pushLog(id, 'ALLOW', `lease issued · ${res.policy_decision ?? ''}`);
      } else {
        sessions.current[id] = { ...blankSession(), phase: 'denied' };
        const hold = res.final_decision === 'HOLD';
        patch(id, {
          lamp: hold ? 'hold' : 'block', lampLabel: null,
          reasons: res.reasons?.length ? res.reasons : [res.policy_decision].filter(Boolean),
          lease: null, ai,
        });
        pushLog(id, hold ? 'HOLD' : 'BLOCK', (res.reasons ?? []).join(', ') || res.policy_decision || '');
      }
    } catch (err) {
      sessions.current[id] = { ...blankSession(), phase: 'denied' };
      const missing = err.status === 404;
      patch(id, {
        lamp: 'block',
        lampLabel: missing ? 'GATEWAY MISSING' : 'API ERROR',
        reasons: [missing ? 'TELEOP_GATEWAY_NOT_DEPLOYED' : String(err.message)],
        lease: null,
      });
      pushLog(id, 'ERROR', String(err.message));
    } finally {
      sessions.current[id].inflight = false;
    }
  }, [patch, pushLog]);

  /* ---------------------------------------------------------------- move */
  const sendPacket = useCallback(async (id, point, speed) => {
    const s = sessions.current[id];
    s.inflight = true;
    s.sequence += 1;                         // strictly increasing per session
    const sequence = s.sequence;
    try {
      const res = await teleopMove(cfgRef.current, {
        controlId: s.controlId, sequence, x: point.x, y: point.y, speed,
      });
      if (res?.status && res.status !== 'EXECUTED' && res.status !== 'QUEUED') {
        const reasons = rejectionReasons(res);
        const label = reasons.join(', ') || res.status;
        pushLog(id, 'BLOCK', label);
        patch(id, { lamp: 'block', lampLabel: res.status, reasons: reasons.length ? reasons : [res.status] });
        await stopSession(id, 'REJECTED_BY_BACKEND');
      }
    } catch (err) {
      /* Fail closed: any rejected packet ends the session immediately. */
      const fromBody = rejectionReasons(err.body);
      const reasons = fromBody.length ? fromBody : [String(err.message)];
      patch(id, {
        lamp: 'block',
        lampLabel: err.status === 409 ? 'LEASE INVALID' : 'REJECTED',
        reasons,
      });
      pushLog(id, 'BLOCK', reasons.join(', '));
      await stopSession(id, 'REJECTED_BY_BACKEND');
    } finally {
      const cur = sessions.current[id];
      if (cur) cur.inflight = false;
    }
  }, [patch, pushLog, stopSession]);

  /* ------------------------------------------------------------- gamepad */
  const pollGamepad = useCallback(() => {
    if (!navigator.getGamepads) return;
    const pad = Array.from(navigator.getGamepads()).find(Boolean);
    if (!pad) return;
    const next = { legit: null, rogue: null };
    PANEL_IDS.forEach((id, i) => {
      const x = pad.axes[i * 2] ?? 0;
      const y = -(pad.axes[i * 2 + 1] ?? 0);
      const mag = Math.min(1, Math.hypot(x, y));
      const s = sessions.current[id];
      if (mag > DEADZONE) {
        sticks.current[id] = { vec: { x, y }, mag };
        next[id] = { vec: { x, y }, mag };
        s.padActive = true;
      } else if (s.padActive) {
        sticks.current[id] = blankStick();
        s.padActive = false;
      }
    });
    setExternal(next);
  }, []);

  /* ------------------------------------------------------------ the loop */
  useEffect(() => {
    const hz = teleopConfig.stream_hz || 8;
    const tickMs = Math.max(60, Math.round(1000 / hz));

    const tick = () => {
      pollGamepad();
      const conf = teleopRef.current;
      const maxSpeed = conf.max_speed ?? 1.5;
      const setpoints = [];

      for (const id of PANEL_IDS) {
        const stick = sticks.current[id];
        const s = sessions.current[id];

        if (stick.mag <= DEADZONE) {
          if (s.phase === 'streaming' || s.phase === 'starting') stopSession(id, 'JOYSTICK_RELEASED');
          else if (s.phase === 'denied') { /* keep the verdict on screen until re-grab */ }
          continue;
        }

        const overspeed = id === 'rogue' && optionsRef.current.overspeed;
        const speed = speedFor(stick.mag, { maxSpeed, overspeed });

        /* Without a real pose we cannot compute a setpoint honestly. */
        const base = robotRef.current;
        if (!base) {
          patch(id, { speed, zone: null, setpoint: null });
          continue;
        }

        const len = Math.hypot(stick.vec.x, stick.vec.y) || 1;
        const bounds = conf.__bounds ?? null;
        let sp = {
          x: base.x + (stick.vec.x / len) * LOOKAHEAD,
          y: base.y + (stick.vec.y / len) * LOOKAHEAD,
        };
        if (bounds) {
          sp = { x: clamp(sp.x, bounds[0], bounds[2]), y: clamp(sp.y, bounds[1], bounds[3]) };
        }
        setpoints.push({ id, sp });
        patch(id, { speed, zone: zoneAt(sp.x, sp.y, conf.zones), setpoint: sp });

        if (s.inflight) continue;

        if (s.phase === 'idle') { startSession(id, sp, speed); continue; }
        if (s.phase === 'streaming') {
          if (Date.now() >= s.expiresAt) {
            /* Lease aged out mid-hold: re-authorize rather than keep streaming. */
            pushLog(id, 'HOLD', 'lease expired — re-authorizing');
            sessions.current[id] = blankSession();
            startSession(id, sp, speed);
            continue;
          }
          sendPacket(id, sp, speed);
        }
      }

      setWorld((prev) => ({ ...prev, setpoints }));
    };

    const handle = setInterval(tick, tickMs);
    return () => clearInterval(handle);
  }, [teleopConfig, patch, pollGamepad, pushLog, sendPacket, startSession, stopSession]);

  /* ------------------------------------------------------ state polling */
  useEffect(() => {
    let alive = true;
    let handle;

    const poll = async () => {
      const c = cfgRef.current;
      try {
        const s = await getState(c);
        const bridge = s.isaac_bridge_state ?? null;
        const pos = readPosition(bridge);
        if (pos) {
          robotRef.current = pos;
          const last = trailRef.current[trailRef.current.length - 1];
          if (!last || Math.hypot(last.x - pos.x, last.y - pos.y) > 0.05) {
            trailRef.current = [...trailRef.current.slice(-399), pos];
          }
        }
        if (alive) {
          setStatus({
            robot_status: s.robot_status, robot_zone: s.robot_zone,
            credential_status: s.credential_status, agent_status: s.agent_status,
            robot_speed: s.robot_speed, protection_enabled: s.protection_enabled,
            last_containment_ack: s.last_containment_ack,
            bridge, online: true,
          });
          setWorld((prev) => ({
            ...prev,
            robot: pos,
            target: readPosition({ position: bridge?.target }),
            trail: trailRef.current,
          }));
        }
      } catch {
        if (alive) setStatus((prev) => ({ ...prev, online: false, robot_status: 'API DOWN' }));
      }

      const [ev, tl] = await Promise.allSettled([getEvents(c), getTimeline(c)]);
      if (!alive) return;
      if (ev.status === 'fulfilled') setEvents(ev.value.slice(0, 12));
      if (tl.status === 'fulfilled') setTimeline(tl.value);

      const active = PANEL_IDS.some((id) => sessions.current[id].phase === 'streaming');
      handle = setTimeout(poll, active ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    };

    poll();
    return () => { alive = false; clearTimeout(handle); };
  }, [cfg.api]);

  /* --------------------------------------------------------------- health */
  useEffect(() => {
    let alive = true;
    getHealth(cfgRef.current).then((h) => alive && setHealth(h)).catch(() => alive && setHealth(null));
    return () => { alive = false; };
  }, [cfg.api]);

  /* -------------------------------------------------------------- gamepad ui */
  useEffect(() => {
    const refresh = () => {
      if (!navigator.getGamepads) { setPadLabel('Gamepad: needs https or 127.0.0.1'); return; }
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

  /* --------------------------------------------------------------- deadman
   * The backend runs the authoritative deadman. The UI still stops proactively
   * so a hidden tab or lost focus does not rely on a timeout to halt motion. */
  useEffect(() => {
    const halt = (reason) => {
      for (const id of PANEL_IDS) {
        sticks.current[id] = blankStick();
        if (sessions.current[id].phase !== 'idle') stopSession(id, reason);
      }
    };
    const onVisibility = () => { if (document.hidden) halt('PAGE_HIDDEN'); };
    const onBlur = () => halt('WINDOW_BLUR');
    const onHide = () => halt('PAGE_HIDE');
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('blur', onBlur);
    window.addEventListener('pagehide', onHide);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('blur', onBlur);
      window.removeEventListener('pagehide', onHide);
      halt('COMPONENT_UNMOUNTED');
    };
  }, [stopSession]);

  /* ---------------------------------------------------------------- reset */
  const reset = useCallback(async () => {
    setResetting(true);
    for (const id of PANEL_IDS) {
      sticks.current[id] = blankStick();
      if (sessions.current[id].phase !== 'idle') await stopSession(id, 'DEMO_RESET');
      sessions.current[id] = blankSession();
    }
    setOptions({ overspeed: false });
    setView(fromEntries(blankView));
    try { await resetBackend(cfgRef.current); } catch { /* surfaced by the poll */ }
    /* Security state is reset; physical position is NOT invented — the next
     * poll reports wherever Isaac actually left the robot. */
    trailRef.current = [];
    setEvents([]);
    setTimeline([]);
    setWorld((prev) => ({ ...prev, trail: [], setpoints: [] }));
    setResetting(false);
  }, [stopSession]);

  return {
    view, world, status, events, timeline, health,
    teleopConfig, gatewayReady,
    options, setOptions, setStick, external, padLabel, reset, resetting,
  };
}
