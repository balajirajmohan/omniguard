import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {
  DEADZONE,
  FALLBACK_TELEOP_CONFIG,
  LOOKAHEAD,
  clamp,
  getEvents,
  getHealth,
  getState,
  getTeleopConfig,
  getTimeline,
  padEstopPressed,
  padStickFor,
  readManipulator,
  readPosition,
  rejectionReasons,
  resetBackend,
  speedFor,
  teleopArmPreset,
  teleopGripper,
  teleopMove,
  teleopStart,
  teleopStop,
  zoneAt,
  simulationRoute,
} from "./omniguard.js";

const PANEL_IDS = ["legit", "rogue"];

/* Speed requested when taking a lease purely to actuate the arm. 0.8 m/s is
 * what the documented curl flow uses and sits inside the band the risk model
 * treats as routine, so authorising the arm does not read as an anomaly. */
const AUX_LEASE_SPEED = 0.8;
/* Renew rather than gamble on a lease that is about to lapse mid-request. */
const AUX_LEASE_MARGIN_MS = 3000;

/* Physical button -> command. Preset and action names mirror the sets
 * backend/teleop.py validates against; anything else is INVALID_ARM_PRESET /
 * INVALID_GRIPPER_ACTION server-side. */
/* Standard-mapping button indices. The gripper is split by plane so each side
 * of the pad belongs to one control plane, mirroring the thumbsticks:
 * left shoulders drive the valid operator, right shoulders drive the hacker.
 * The hacker's presses are expected to be rejected -- that is the demo. */
export const AUX_BUTTONS = [
  [12, (a) => a.armPreset("reach")],
  [13, (a) => a.armPreset("stow")],
  [14, (a) => a.armPreset("carry")],
  [15, (a) => a.armPreset("inspect")],
  [4, (a) => a.gripperFor("legit", "open")], // L1
  [6, (a) => a.gripperFor("legit", "close")], // L2
  [5, (a) => a.gripperFor("rogue", "open")], // R1
  [7, (a) => a.gripperFor("rogue", "close")], // R2
];
const IDLE_POLL_MS = 1500;
const ACTIVE_POLL_MS = 350;
const SIMULATION_SPEED = 0.8;
const SIMULATION_ARRIVAL_M = 0.35;
const SIMULATION_RESUME_MS = 3000;

const blankStick = () => ({vec: {x: 0, y: 0}, mag: 0});
const blankSession = () => ({
  phase: "idle", // idle | starting | streaming | denied
  controlId: null,
  expiresAt: 0,
  maxSpeed: null,
  allowedZones: null,
  sequence: 0,
  inflight: false,
  padActive: false,
});
const blankView = () => ({
  lamp: "idle",
  lampLabel: null,
  speed: 0,
  zone: null,
  setpoint: null,
  reasons: [],
  log: [],
  lease: null,
  ai: null,
});
const blankSimulation = () => ({
  enabled: false,
  scenario: null,
  phase: "stopped", // stopped | running | override | resuming
  destination: null,
  objective: null,
  waypointIndex: 0,
  routeStarted: true,
  legsInCycle: 0,
  completedLegs: 0,
  completedCycles: 0,
  resumeAt: null,
});

const fromEntries = (fn) =>
  Object.fromEntries(PANEL_IDS.map((id) => [id, fn(id)]));
let logSeq = 0;

export function useController(cfg) {
  const cfgRef = useRef(cfg);
  cfgRef.current = cfg;

  const sticks = useRef(fromEntries(blankStick));
  const sessions = useRef(fromEntries(blankSession));
  /* Arm and gripper need a lease, but they are not movement, so they must not
   * depend on a stick being held. These are short-lived leases taken on demand
   * exactly as the documented curl flow does: start, then actuate. */
  const auxLeases = useRef(fromEntries(() => null));
  /* A held button can ask for a lease many times before the first answer comes
   * back. Without this, every one of those calls opens its own lease and the
   * backend sees a storm of teleop_start. */
  const leaseInflight = useRef(fromEntries(() => null));

  const [teleopConfig, setTeleopConfig] = useState(FALLBACK_TELEOP_CONFIG);
  const [gatewayReady, setGatewayReady] = useState(null); // null = unknown
  const teleopRef = useRef(FALLBACK_TELEOP_CONFIG);
  teleopRef.current = teleopConfig;

  const [options, setOptions] = useState({overspeed: false});
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const [view, setView] = useState(() => fromEntries(blankView));
  const [world, setWorld] = useState({
    robot: null,
    target: null,
    setpoints: [],
    trail: [],
    manipulator: null,
  });
  const [status, setStatus] = useState({});
  const [events, setEvents] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [health, setHealth] = useState(null);
  const [padLabel, setPadLabel] = useState("Gamepad: checking…");
  /* Mutable so the pad can drive the sticks at display rate without re-rendering. */
  const padRef = useRef(
    fromEntries(() => ({vec: {x: 0, y: 0}, mag: 0, active: false})),
  );
  const estopRef = useRef(null);
  const auxRef = useRef(null);
  const [resetting, setResetting] = useState(false);
  const [simulation, setSimulation] = useState(blankSimulation);
  const simulationRef = useRef(blankSimulation());

  /* Physical pose, from the backend only. Never estimated — a map that invents
   * a position makes every zone read-out a guess. */
  const robotRef = useRef(null);
  const trailRef = useRef([]);
  /* Last bridge payload, and the last arm/gripper command the backend accepted
   * from this UI. readManipulator prefers the bridge and falls back to these —
   * mock mode never reports arm/gripper at all, so without them the map would
   * stay blank for the whole demo. */
  const bridgeRef = useRef(null);
  const commandedRef = useRef({arm: null, gripper: null});

  const patch = useCallback((id, next) => {
    setView((prev) => ({...prev, [id]: {...prev[id], ...next}}));
  }, []);

  const pushLog = useCallback((id, decision, detail) => {
    setView((prev) => {
      const log = [
        {
          id: ++logSeq,
          time: new Date().toLocaleTimeString([], {hour12: false}),
          decision,
          detail,
        },
        ...prev[id].log,
      ].slice(0, 40);
      return {...prev, [id]: {...prev[id], log}};
    });
  }, []);

  const setStick = useCallback((id, next) => {
    sticks.current[id] = next;
  }, []);

  const publishSimulation = useCallback((next) => {
    simulationRef.current = next;
    setSimulation(next);
  }, []);

  /* --------------------------------------------------------------- config */
  useEffect(() => {
    let alive = true;
    getTeleopConfig(cfgRef.current)
      .then((c) => {
        if (alive) {
          setTeleopConfig(c);
          setGatewayReady(true);
        }
      })
      .catch(() => {
        if (alive) {
          setTeleopConfig(FALLBACK_TELEOP_CONFIG);
          setGatewayReady(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [cfg.api]);

  /* ---------------------------------------------------------------- stop */
  const stopSession = useCallback(
    async (id, reason) => {
      const s = sessions.current[id];
      const controlId = s.controlId;
      sessions.current[id] = blankSession();
      patch(id, {
        lamp: "idle",
        lampLabel: null,
        reasons: [],
        lease: null,
        speed: 0,
        zone: null,
        setpoint: null,
      });
      if (!controlId) return;
      try {
        await teleopStop(cfgRef.current, {controlId, reason});
      } catch {
        /* The backend deadman is the real guarantee; a failed stop call must not
         * throw into the loop. */
      }
    },
    [patch],
  );

  /* An aux lease outlives the press that created it, so every stop path has to
   * hand it back — otherwise the robot stays leased after an emergency stop. */
  const releaseAuxLease = useCallback(async (id, reason) => {
    const held = auxLeases.current[id];
    if (!held) return;
    auxLeases.current[id] = null;
    try {
      await teleopStop(cfgRef.current, {controlId: held.controlId, reason});
    } catch {
      /* The backend lease TTL is the real guarantee. */
    }
  }, []);

  const deactivateSimulation = useCallback(() => {
    if (!simulationRef.current.enabled) return false;
    publishSimulation(blankSimulation());
    return true;
  }, [publishSimulation]);

  const stopSimulation = useCallback(async () => {
    if (!deactivateSimulation()) return;
    sticks.current.legit = blankStick();
    if (sessions.current.legit.phase !== "idle") {
      await stopSession("legit", "SIMULATION_STOPPED");
    }
    await releaseAuxLease("legit", "SIMULATION_STOPPED");
    pushLog("legit", "STOP", "simulation stopped · live control restored");
  }, [deactivateSimulation, pushLog, releaseAuxLease, stopSession]);

  const startSimulation = useCallback(
    async (scenario = "zone-shuttle") => {
      if (!robotRef.current) return false;
      const zones = teleopRef.current.zones;
      const route = simulationRoute(zones, scenario);
      if (!route?.length) return false;

      sticks.current.legit = blankStick();
      if (sessions.current.legit.phase !== "idle") {
        await stopSession("legit", "SIMULATION_STARTED");
      }
      await releaseAuxLease("legit", "SIMULATION_STARTED");

      const currentZone = zoneAt(robotRef.current.x, robotRef.current.y, zones);
      let waypointIndex = 0;
      if (scenario === "zone-shuttle") {
        waypointIndex = currentZone === "SAFE_ZONE_A" ? 1 : 0;
      } else {
        waypointIndex = route.reduce(
          (nearest, point, index) => {
            const distance = Math.hypot(
              point.x - robotRef.current.x,
              point.y - robotRef.current.y,
            );
            return distance < nearest.distance ? {index, distance} : nearest;
          },
          {index: 0, distance: Infinity},
        ).index;
      }
      const waypoint = route[waypointIndex];
      publishSimulation({
        enabled: true,
        scenario,
        phase: "running",
        destination: waypoint.id,
        objective: waypoint.label,
        waypointIndex,
        routeStarted: scenario === "zone-shuttle",
        legsInCycle: 0,
        completedLegs: 0,
        completedCycles: 0,
        resumeAt: null,
      });
      pushLog(
        "legit",
        "ALLOW",
        `simulation started · proceeding to ${waypoint.label}`,
      );
      return true;
    },
    [publishSimulation, pushLog, releaseAuxLease, stopSession],
  );

  /* --------------------------------------------------------------- start */
  const startSession = useCallback(
    async (id, point, speed) => {
      const s = sessions.current[id];
      s.phase = "starting";
      s.inflight = true;
      patch(id, {lamp: "idle", lampLabel: "AUTHORIZING"});
      try {
        const res = await teleopStart(cfgRef.current, id, {...point, speed});
        const ai = res.ai ?? null;
        if (res.final_decision === "ALLOW" && res.control_id) {
          sessions.current[id] = {
            ...blankSession(),
            phase: "streaming",
            controlId: res.control_id,
            expiresAt: res.expires_at
              ? Date.parse(res.expires_at)
              : Date.now() + 30_000,
            maxSpeed: res.max_speed ?? null,
            allowedZones: res.allowed_zones ?? null,
            sequence: 0,
          };
          patch(id, {
            lamp: "allow",
            lampLabel: "LEASE ACTIVE",
            reasons: [res.policy_decision].filter(Boolean),
            lease: {
              controlId: res.control_id,
              expiresAt: res.expires_at,
              maxSpeed: res.max_speed,
              allowedZones: res.allowed_zones,
            },
            ai,
          });
          pushLog(id, "ALLOW", `lease issued · ${res.policy_decision ?? ""}`);
        } else {
          sessions.current[id] = {...blankSession(), phase: "denied"};
          const hold = res.final_decision === "HOLD";
          patch(id, {
            lamp: hold ? "hold" : "block",
            lampLabel: null,
            reasons: res.reasons?.length
              ? res.reasons
              : [res.policy_decision].filter(Boolean),
            lease: null,
            ai,
          });
          pushLog(
            id,
            hold ? "HOLD" : "BLOCK",
            (res.reasons ?? []).join(", ") || res.policy_decision || "",
          );
        }
      } catch (err) {
        sessions.current[id] = {...blankSession(), phase: "denied"};
        const missing = err.status === 404;
        patch(id, {
          lamp: "block",
          lampLabel: missing ? "GATEWAY MISSING" : "API ERROR",
          reasons: [
            missing ? "TELEOP_GATEWAY_NOT_DEPLOYED" : String(err.message),
          ],
          lease: null,
        });
        pushLog(id, "ERROR", String(err.message));
      } finally {
        sessions.current[id].inflight = false;
      }
    },
    [patch, pushLog],
  );

  /* ---------------------------------------------------------------- move */
  const sendPacket = useCallback(
    async (id, point, speed) => {
      const s = sessions.current[id];
      s.inflight = true;
      s.sequence += 1; // strictly increasing per session
      const sequence = s.sequence;
      try {
        const res = await teleopMove(cfgRef.current, {
          controlId: s.controlId,
          sequence,
          x: point.x,
          y: point.y,
          speed,
        });
        if (
          res?.status &&
          res.status !== "EXECUTED" &&
          res.status !== "QUEUED"
        ) {
          const reasons = rejectionReasons(res);
          const label = reasons.join(", ") || res.status;
          pushLog(id, "BLOCK", label);
          patch(id, {
            lamp: "block",
            lampLabel: res.status,
            reasons: reasons.length ? reasons : [res.status],
          });
          await stopSession(id, "REJECTED_BY_BACKEND");
        }
      } catch (err) {
        /* Fail closed: any rejected packet ends the session immediately. */
        const fromBody = rejectionReasons(err.body);
        const reasons = fromBody.length ? fromBody : [String(err.message)];
        patch(id, {
          lamp: "block",
          lampLabel: err.status === 409 ? "LEASE INVALID" : "REJECTED",
          reasons,
        });
        pushLog(id, "BLOCK", reasons.join(", "));
        await stopSession(id, "REJECTED_BY_BACKEND");
      } finally {
        const cur = sessions.current[id];
        if (cur) cur.inflight = false;
      }
    },
    [patch, pushLog, stopSession],
  );

  /* ------------------------------------------------------------- gamepad
   * Sampled on requestAnimationFrame (display rate), NOT on the send tick.
   * Sending at stream_hz is correct; sampling a physical stick at 8 Hz makes it
   * feel stepped. Results go into refs so 60 Hz of stick motion causes zero
   * React re-renders — the send loop and the thumb both read the ref.
   *
   * Standard mapping (DualSense over USB or Bluetooth reports "standard"):
   *   axes[0..1] left stick -> operator      axes[2..3] right stick -> attacker
   *   buttons[1] Circle -> emergency stop
   */
  useEffect(() => {
    if (!navigator.getGamepads) {
      setPadLabel("Gamepad: needs https or 127.0.0.1");
      return undefined;
    }

    let frame;
    let estopWasDown = false;
    const auxWasDown = {};
    let lastId = null;

    const sample = () => {
      const pad = Array.from(navigator.getGamepads?.() ?? []).find(Boolean);

      if (!pad) {
        if (lastId !== null) {
          lastId = null;
          /* Chrome exposes nothing until the pad sends input, so "none" is not
           * the same as "not plugged in". Say what actually unblocks it. */
          setPadLabel("Gamepad: press any button to connect");
          for (const id of PANEL_IDS) {
            if (padRef.current[id].active) {
              padRef.current[id] = {
                vec: {x: 0, y: 0},
                mag: 0,
                active: false,
              };
              sticks.current[id] = blankStick();
            }
          }
        }
        frame = requestAnimationFrame(sample);
        return;
      }

      if (pad.index !== lastId) {
        lastId = pad.index;
        const nonStandard = pad.mapping !== "standard";
        setPadLabel(
          `Gamepad: ${pad.id.slice(0, 28)}${nonStandard ? " (non-standard mapping)" : ""}`,
        );
      }

      PANEL_IDS.forEach((id, i) => {
        const next = padStickFor(pad, i);
        const slot = padRef.current[id];
        if (next.active) {
          padRef.current[id] = next;
          sticks.current[id] = {vec: next.vec, mag: next.mag};
        } else if (slot.active) {
          /* Released: publish an explicit zero so the thumb springs back.
           * Publishing null here is what used to leave it stuck deflected. */
          padRef.current[id] = next;
          sticks.current[id] = blankStick();
        }
      });

      /* Standard mapping: L1=4 R1=5, d-pad up/down/left/right = 12/13/14/15.
       * Rising edge only — a held button must not stream commands. */
      const aux = auxRef.current;
      if (aux) {
        for (const [index, fire] of AUX_BUTTONS) {
          const down = pad.buttons?.[index]?.pressed === true;
          if (down && !auxWasDown[index]) fire(aux);
          auxWasDown[index] = down;
        }
      }

      const estop = padEstopPressed(pad);
      if (estop && !estopWasDown) {
        for (const id of PANEL_IDS) {
          padRef.current[id] = {vec: {x: 0, y: 0}, mag: 0, active: false};
          sticks.current[id] = blankStick();
        }
        estopRef.current?.();
      }
      estopWasDown = estop;

      frame = requestAnimationFrame(sample);
    };

    frame = requestAnimationFrame(sample);
    return () => cancelAnimationFrame(frame);
  }, []);

  /* ------------------------------------------------------------ the loop */
  useEffect(() => {
    const hz = teleopConfig.stream_hz || 8;
    const tickMs = Math.max(60, Math.round(1000 / hz));

    const tick = () => {
      const conf = teleopRef.current;
      const maxSpeed = conf.max_speed ?? 1.5;
      const setpoints = [];

      for (const id of PANEL_IDS) {
        const manualStick = sticks.current[id];
        let stick = manualStick;
        let autonomousPoint = null;
        const s = sessions.current[id];

        /* The autonomous duty is a virtual legitimate operator, not a bridge
         * shortcut. It enters this exact lease/sequence/policy loop. Physical
         * operator input has priority and the route resumes only after 3 s idle. */
        if (id === "legit" && simulationRef.current.enabled) {
          let sim = simulationRef.current;
          const manual = manualStick.mag > DEADZONE;

          if (manual && sim.phase !== "override") {
            sim = {...sim, phase: "override", resumeAt: null};
            publishSimulation(sim);
            pushLog(
              "legit",
              "HOLD",
              "manual override · autonomous route paused",
            );
          } else if (!manual && sim.phase === "override") {
            sim = {
              ...sim,
              phase: "resuming",
              resumeAt: Date.now() + SIMULATION_RESUME_MS,
            };
            publishSimulation(sim);
            pushLog(
              "legit",
              "HOLD",
              "operator released · route resumes after 3 s idle",
            );
          } else if (
            !manual &&
            sim.phase === "resuming" &&
            Date.now() >= sim.resumeAt
          ) {
            sim = {...sim, phase: "running", resumeAt: null};
            publishSimulation(sim);
            pushLog(
              "legit",
              "ALLOW",
              `simulation resumed · proceeding to ${sim.objective}`,
            );
          }

          if (!manual && sim.phase === "running") {
            const base = robotRef.current;
            const route = simulationRoute(conf.zones, sim.scenario);
            let waypoint = route?.[sim.waypointIndex] ?? null;
            if (
              base &&
              waypoint &&
              Math.hypot(waypoint.x - base.x, waypoint.y - base.y) <=
                SIMULATION_ARRIVAL_M
            ) {
              const completedRouteLeg = sim.routeStarted;
              const waypointIndex = (sim.waypointIndex + 1) % route.length;
              const legsInCycle = completedRouteLeg
                ? (sim.legsInCycle + 1) % route.length
                : 0;
              const completedCycles =
                sim.completedCycles +
                (completedRouteLeg && legsInCycle === 0 ? 1 : 0);
              waypoint = route[waypointIndex];
              sim = {
                ...sim,
                waypointIndex,
                destination: waypoint.id,
                objective: waypoint.label,
                routeStarted: true,
                legsInCycle,
                completedLegs: sim.completedLegs + (completedRouteLeg ? 1 : 0),
                completedCycles,
              };
              publishSimulation(sim);
              pushLog(
                "legit",
                "ALLOW",
                `${completedRouteLeg ? "route leg complete" : "patrol entry reached"} · proceeding to ${waypoint.label}`,
              );
            }
            if (base && waypoint) {
              autonomousPoint = waypoint;
              stick = {
                vec: {x: waypoint.x - base.x, y: waypoint.y - base.y},
                mag: 1,
              };
            }
          } else if (!manual) {
            stick = blankStick();
          }
        }

        if (stick.mag <= DEADZONE) {
          if (s.phase === "streaming" || s.phase === "starting")
            stopSession(id, "JOYSTICK_RELEASED");
          else if (s.phase === "denied") {
            /* keep the verdict on screen until re-grab */
          }
          continue;
        }

        const overspeed = id === "rogue" && optionsRef.current.overspeed;
        const speed = autonomousPoint
          ? Math.min(SIMULATION_SPEED, maxSpeed)
          : speedFor(stick.mag, {maxSpeed, overspeed});

        /* Without a real pose we cannot compute a setpoint honestly. */
        const base = robotRef.current;
        if (!base) {
          patch(id, {speed, zone: null, setpoint: null});
          continue;
        }

        const len = Math.hypot(stick.vec.x, stick.vec.y) || 1;
        const bounds = conf.__bounds ?? null;
        let sp = autonomousPoint ?? {
          x: base.x + (stick.vec.x / len) * LOOKAHEAD,
          y: base.y + (stick.vec.y / len) * LOOKAHEAD,
        };
        if (bounds) {
          sp = {
            x: clamp(sp.x, bounds[0], bounds[2]),
            y: clamp(sp.y, bounds[1], bounds[3]),
          };
        }
        setpoints.push({id, sp});
        patch(id, {
          speed,
          zone: zoneAt(sp.x, sp.y, conf.zones),
          setpoint: sp,
        });

        if (s.inflight) continue;

        if (s.phase === "idle") {
          startSession(id, sp, speed);
          continue;
        }
        if (s.phase === "streaming") {
          if (Date.now() >= s.expiresAt) {
            /* Lease aged out mid-hold: re-authorize rather than keep streaming. */
            pushLog(id, "HOLD", "lease expired — re-authorizing");
            sessions.current[id] = blankSession();
            startSession(id, sp, speed);
            continue;
          }
          sendPacket(id, sp, speed);
        }
      }

      setWorld((prev) => ({...prev, setpoints}));
    };

    const handle = setInterval(tick, tickMs);
    return () => clearInterval(handle);
  }, [teleopConfig, patch, pushLog, sendPacket, startSession, stopSession]);

  /* ------------------------------------------------------ state polling */
  useEffect(() => {
    let alive = true;
    let handle;
    let consecutiveFailures = 0;

    const poll = async () => {
      const c = cfgRef.current;
      try {
        const s = await getState(c);
        const bridge = s.isaac_bridge_state ?? null;
        bridgeRef.current = bridge;
        const pos = readPosition(bridge);
        if (pos) {
          robotRef.current = pos;
          const last = trailRef.current[trailRef.current.length - 1];
          if (!last || Math.hypot(last.x - pos.x, last.y - pos.y) > 0.05) {
            trailRef.current = [...trailRef.current.slice(-399), pos];
          }
        }
        consecutiveFailures = 0;
        if (alive) {
          setStatus({
            robot_status: s.robot_status,
            robot_zone: s.robot_zone,
            credential_status: s.credential_status,
            agent_status: s.agent_status,
            robot_speed: s.robot_speed,
            protection_enabled: s.protection_enabled,
            last_containment_ack: s.last_containment_ack,
            bridge,
            online: true,
            connection: "ONLINE",
            last_successful_update: new Date().toISOString(),
          });
          setWorld((prev) => ({
            ...prev,
            robot: pos,
            target: readPosition({position: bridge?.target}),
            trail: trailRef.current,
            manipulator: readManipulator(bridge, commandedRef.current),
          }));
        }
      } catch {
        consecutiveFailures += 1;
        if (alive) {
          setStatus((prev) => {
            if (consecutiveFailures >= 3) {
              return {
                ...prev,
                online: false,
                connection: "OFFLINE",
                robot_status: "API DOWN",
              };
            }
            // Preserve last known robot fields; mark degraded after first failure.
            return {
              ...prev,
              online: consecutiveFailures < 3,
              connection: "DEGRADED",
            };
          });
        }
      }

      const [ev, tl] = await Promise.allSettled([getEvents(c), getTimeline(c)]);
      if (!alive) return;
      if (ev.status === "fulfilled") setEvents(ev.value.slice(0, 12));
      if (tl.status === "fulfilled") setTimeline(tl.value);

      const active = PANEL_IDS.some(
        (id) => sessions.current[id].phase === "streaming",
      );
      handle = setTimeout(poll, active ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    };

    poll();
    return () => {
      alive = false;
      clearTimeout(handle);
    };
  }, [cfg.api]);

  /* --------------------------------------------------------------- health */
  useEffect(() => {
    let alive = true;
    getHealth(cfgRef.current)
      .then((h) => alive && setHealth(h))
      .catch(() => alive && setHealth(null));
    return () => {
      alive = false;
    };
  }, [cfg.api]);

  /* --------------------------------------------------------------- deadman
   * The backend runs the authoritative deadman. The UI still stops proactively
   * so a hidden tab or lost focus does not rely on a timeout to halt motion. */
  useEffect(() => {
    const halt = (reason) => {
      deactivateSimulation();
      for (const id of PANEL_IDS) {
        sticks.current[id] = blankStick();
        if (sessions.current[id].phase !== "idle") stopSession(id, reason);
      }
    };
    const onVisibility = () => {
      if (document.hidden) halt("PAGE_HIDDEN");
    };
    const onBlur = () => halt("WINDOW_BLUR");
    const onHide = () => halt("PAGE_HIDE");
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    window.addEventListener("pagehide", onHide);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("pagehide", onHide);
      halt("COMPONENT_UNMOUNTED");
    };
  }, [deactivateSimulation, stopSession]);

  /* Physical stop button on the pad. Routed through the same backend stop the
   * software paths use — it is not a client-side shortcut around the broker. */
  useEffect(() => {
    estopRef.current = () => {
      deactivateSimulation();
      for (const id of PANEL_IDS) {
        if (sessions.current[id].phase !== "idle")
          stopSession(id, "GAMEPAD_EMERGENCY_STOP");
      }
    };
    return () => {
      estopRef.current = null;
    };
  }, [deactivateSimulation, stopSession]);

  const emergencyStop = useCallback(() => {
    deactivateSimulation();
    for (const id of PANEL_IDS) {
      sticks.current[id] = blankStick();
      if (sessions.current[id].phase !== "idle")
        stopSession(id, "EMERGENCY_STOP");
      releaseAuxLease(id, "EMERGENCY_STOP");
    }
  }, [deactivateSimulation, stopSession, releaseAuxLease]);

  /* ------------------------------------------------------------- arm/grip
   * Arm and gripper commands ride the same teleop lease as movement: without an
   * active lease there is nothing to authorize them, and a rejection tears the
   * lease down exactly like a rejected movement packet. */
  /* A lease for an arm/gripper press: reuse the movement lease if the stick is
   * held, reuse a still-valid aux lease, otherwise take a fresh one. Taking one
   * runs the full risk evaluation, so a hacker's gripper press produces a real
   * verdict rather than a generic "no lease". */
  const ensureLease = useCallback(
    async (id) => {
      const moving = sessions.current[id]?.controlId;
      if (moving) return moving;

      const held = auxLeases.current[id];
      if (held && held.expiresAt - Date.now() > AUX_LEASE_MARGIN_MS)
        return held.controlId;

      if (leaseInflight.current[id]) return leaseInflight.current[id];

      /* Target the pose the robot already holds, so taking the lease authorises
       * the arm without also commanding the base to move. */
      const point = robotRef.current ?? {x: 0, y: 0};
      patch(id, {lamp: "idle", lampLabel: "AUTHORIZING"});
      const attempt = (async () => {
        try {
          const res = await teleopStart(cfgRef.current, id, {
            ...point,
            speed: AUX_LEASE_SPEED,
          });
          const ai = res.ai ?? null;
          if (res.final_decision === "ALLOW" && res.control_id) {
            auxLeases.current[id] = {
              controlId: res.control_id,
              expiresAt: res.expires_at
                ? Date.parse(res.expires_at)
                : Date.now() + 30_000,
            };
            patch(id, {
              lamp: "allow",
              lampLabel: "LEASE ACTIVE",
              reasons: [res.policy_decision].filter(Boolean),
              lease: {
                controlId: res.control_id,
                expiresAt: res.expires_at,
                maxSpeed: res.max_speed,
              },
              ai,
            });
            return res.control_id;
          }
          auxLeases.current[id] = null;
          const hold = res.final_decision === "HOLD";
          patch(id, {
            lamp: hold ? "hold" : "block",
            lampLabel: null,
            reasons: res.reasons?.length
              ? res.reasons
              : [res.policy_decision].filter(Boolean),
            lease: null,
            ai,
          });
          pushLog(
            id,
            hold ? "HOLD" : "BLOCK",
            (res.reasons ?? []).join(", ") || res.policy_decision || "",
          );
          return null;
        } catch (err) {
          auxLeases.current[id] = null;
          const missing = err.status === 404;
          patch(id, {
            lamp: "block",
            lampLabel: missing ? "GATEWAY MISSING" : "API ERROR",
            reasons: [
              missing ? "TELEOP_GATEWAY_NOT_DEPLOYED" : String(err.message),
            ],
            lease: null,
          });
          pushLog(id, "ERROR", String(err.message));
          return null;
        }
      })();

      leaseInflight.current[id] = attempt;
      try {
        return await attempt;
      } finally {
        leaseInflight.current[id] = null;
      }
    },
    [patch, pushLog],
  );

  const handleLeaseCommand = useCallback(
    async (id, label, invoke) => {
      const controlId = await ensureLease(id);
      if (!controlId) return false; // ensureLease has already surfaced the verdict
      try {
        const res = await invoke(controlId);
        if (res?.status && !["EXECUTED", "QUEUED"].includes(res.status)) {
          const reasons = rejectionReasons(res);
          sessions.current[id] = blankSession();
          auxLeases.current[id] = null;
          patch(id, {
            lamp: "block",
            lampLabel: res.status,
            reasons,
            lease: null,
          });
          pushLog(id, "BLOCK", reasons.join(", ") || res.status);
          return false;
        }
        pushLog(
          id,
          "ALLOW",
          `${label} ${(res?.status ?? "QUEUED").toLowerCase()}`,
        );
        return true;
      } catch (err) {
        const fromBody = rejectionReasons(err.body);
        const reasons = fromBody.length ? fromBody : [String(err.message)];
        sessions.current[id] = blankSession();
        auxLeases.current[id] = null;
        patch(id, {
          lamp: "block",
          lampLabel: "REJECTED",
          reasons,
          lease: null,
        });
        pushLog(id, "BLOCK", reasons.join(", "));
        return false;
      }
    },
    [ensureLease, patch, pushLog],
  );

  /* Redraw the manipulator the moment a command is accepted rather than waiting
   * up to a poll interval for the next /api/state. */
  const publishManipulator = useCallback(() => {
    setWorld((prev) => ({
      ...prev,
      manipulator: readManipulator(bridgeRef.current, commandedRef.current),
    }));
  }, []);

  const sendArmPreset = useCallback(
    async (id, preset) => {
      const accepted = await handleLeaseCommand(
        id,
        `ARM ${preset}`,
        (controlId) => teleopArmPreset(cfgRef.current, {controlId, preset}),
      );
      if (accepted) {
        commandedRef.current = {...commandedRef.current, arm: preset};
        publishManipulator();
      }
      return accepted;
    },
    [handleLeaseCommand, publishManipulator],
  );

  const sendGripper = useCallback(
    async (id, action) => {
      const accepted = await handleLeaseCommand(
        id,
        `GRIPPER ${action}`,
        (controlId) => teleopGripper(cfgRef.current, {controlId, action}),
      );
      if (accepted) {
        commandedRef.current = {...commandedRef.current, gripper: action};
        publishManipulator();
      }
      return accepted;
    },
    [handleLeaseCommand, publishManipulator],
  );

  /* Arm presets ride whichever plane holds a lease (or is actively driving).
   * With no lease yet, ensureLease() takes a short aux lease via /api/teleop/start
   * so the press still produces a real identity/policy verdict. Gripper shoulders
   * are plane-addressed separately (left = operator, right = hacker). */
  const leaseOwner = useCallback(() => {
    for (const id of PANEL_IDS) if (sessions.current[id].controlId) return id;
    /* No lease: attribute the attempt to whoever is actually driving, so a
     * hacker's blocked arm command is reported on the hacker's panel instead of
     * looking like the operator fumbled.
     *
     * Only live phases count. 'denied' is sticky -- it survives until the plane
     * is grabbed again -- so treating it as driving would permanently redirect
     * every arm press to a plane that can never hold a lease, and every press
     * would come back rejected. */
    for (const id of PANEL_IDS) {
      const phase = sessions.current[id].phase;
      if (phase === "starting" || phase === "streaming") return id;
    }
    return PANEL_IDS[0];
  }, []);

  /* The same three commands the d-pad, shoulders and Circle issue, bound to the
   * lease holder so the keyboard is a peer input rather than a special case. */
  const aux = useMemo(
    () => ({
      armPreset: (preset) => sendArmPreset(leaseOwner(), preset),
      /* Gripper is addressed by plane, so a press always says who is asking. */
      gripperFor: (panel, action) => sendGripper(panel, action),
      emergencyStop,
    }),
    [leaseOwner, sendArmPreset, sendGripper, emergencyStop],
  );

  useEffect(() => {
    auxRef.current = aux;
    return () => {
      auxRef.current = null;
    };
  }, [aux]);

  /* ---------------------------------------------------------------- reset */
  const reset = useCallback(async () => {
    setResetting(true);
    publishSimulation(blankSimulation());
    for (const id of PANEL_IDS) {
      sticks.current[id] = blankStick();
      if (sessions.current[id].phase !== "idle")
        await stopSession(id, "DEMO_RESET");
      await releaseAuxLease(id, "DEMO_RESET");
      sessions.current[id] = blankSession();
    }
    setOptions({overspeed: false});
    setView(fromEntries(blankView));
    try {
      await resetBackend(cfgRef.current);
    } catch {
      /* surfaced by the poll */
    }
    /* Security state is reset; physical position is NOT invented — the next
     * poll reports wherever Isaac actually left the robot. */
    trailRef.current = [];
    commandedRef.current = {arm: null, gripper: null};
    setEvents([]);
    setTimeline([]);
    setWorld((prev) => ({
      ...prev,
      trail: [],
      setpoints: [],
      manipulator: null,
    }));
    setResetting(false);
  }, [publishSimulation, stopSession, releaseAuxLease]);

  return {
    view,
    world,
    status,
    events,
    timeline,
    health,
    teleopConfig,
    gatewayReady,
    options,
    setOptions,
    setStick,
    stickRef: sticks,
    padRef,
    padLabel,
    reset,
    resetting,
    sendArmPreset,
    sendGripper,
    emergencyStop,
    aux,
    simulation,
    startSimulation,
    stopSimulation,
  };
}
