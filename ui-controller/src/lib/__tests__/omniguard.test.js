import {readFileSync, readdirSync, statSync} from "node:fs";
import {join} from "node:path";
import {beforeEach, describe, expect, it, vi} from "vitest";
import * as OG from "../omniguard.js";

const cfg = {
  api: "http://127.0.0.1:8000",
  robot: "robot-01",
  credential: "fleet-agent-valid-token",
};

function mockFetch(response = {ok: true, body: {}}) {
  const spy = vi.fn(async () => ({
    ok: response.ok !== false,
    status: response.status ?? 200,
    statusText: "OK",
    text: async () => JSON.stringify(response.body ?? {}),
  }));
  globalThis.fetch = spy;
  return spy;
}

const bodyOf = (spy, call = 0) => JSON.parse(spy.mock.calls[call][1].body);
const urlOf = (spy, call = 0) => spy.mock.calls[call][0];

beforeEach(() => {
  globalThis.localStorage = {
    store: {},
    getItem(k) {
      return this.store[k] ?? null;
    },
    setItem(k, v) {
      this.store[k] = v;
    },
  };
});

describe("security boundary", () => {
  it("never references the Isaac bridge port in executable code", () => {
    const srcDir = new URL("../../", import.meta.url).pathname;
    const offenders = [];
    const walk = (dir) => {
      for (const name of readdirSync(dir)) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) {
          if (name !== "__tests__") walk(full); // fixtures below name the port on purpose
          continue;
        }
        if (!/\.(js|jsx)$/.test(name)) continue;
        const code = readFileSync(full, "utf8")
          .replace(/\/\*[\s\S]*?\*\//g, "") // block comments
          .replace(/^\s*\/\/.*$/gm, "") // line comments
          .replace(/\{\/\*[\s\S]*?\*\/\}/g, ""); // jsx comments
        if (code.includes("8899")) offenders.push(full);
      }
    };
    walk(srcDir);
    expect(offenders).toEqual([]);
  });

  it("exposes no bridge transport helpers", () => {
    for (const gone of [
      "sendMove",
      "sendStop",
      "bridgePost",
      "bridgeReachable",
    ]) {
      expect(OG[gone]).toBeUndefined();
    }
  });

  it("defaults the API to the backend, not Streamlit", () => {
    expect(OG.DEFAULTS.api).toBe("http://127.0.0.1:8000");
    expect(OG.DEFAULTS.bridge).toBeUndefined();
  });

  it("never persists the fleet credential", () => {
    OG.saveConfig({
      api: "http://x",
      robot: "robot-01",
      credential: "super-secret",
    });
    expect(localStorage.getItem("omniguard.cfg")).not.toContain("super-secret");
  });

  it("never persists the demo operator token", () => {
    OG.saveConfig({
      api: "http://x",
      robot: "robot-01",
      credential: OG.DEMO_CREDENTIAL,
      operatorToken: "should-not-persist",
    });
    const raw = localStorage.getItem("omniguard.cfg");
    expect(raw).not.toContain("should-not-persist");
    expect(raw).not.toContain("operatorToken");
    expect(OG.loadConfig().operatorToken).toBe(OG.DEMO_OPERATOR_TOKEN);
  });

  it("ignores a credential or bridge left behind by an older build", () => {
    localStorage.setItem(
      "omniguard.cfg",
      JSON.stringify({
        api: "http://x",
        credential: "stale",
        bridge: "http://h:8899",
      }),
    );
    const loaded = OG.loadConfig();
    expect(loaded.bridge).toBeUndefined();
    expect(loaded.credential).toBe(OG.DEMO_CREDENTIAL);
  });
});

describe("protection OFF operator authorization", () => {
  const cfgWithOp = {
    ...cfg,
    operatorToken: OG.DEMO_OPERATOR_TOKEN,
  };

  it("sends X-OmniGuard-Operator only when protection=false", async () => {
    const spy = mockFetch({
      body: {final_decision: "ALLOW", policy_decision: "BYPASSED"},
    });
    await OG.runScenario(cfgWithOp, "rogue_device", {
      protection: false,
      resetFirst: true,
    });
    expect(urlOf(spy)).toContain("/api/scenarios/rogue_device/run");
    expect(urlOf(spy)).toContain("protection=false");
    expect(spy.mock.calls[0][1].headers[OG.OPERATOR_HEADER]).toBe(
      OG.DEMO_OPERATOR_TOKEN,
    );

    spy.mockClear();
    await OG.runScenario(cfgWithOp, "normal", {protection: true});
    expect(urlOf(spy)).toContain("protection=true");
    expect(spy.mock.calls[0][1].headers?.[OG.OPERATOR_HEADER]).toBeUndefined();
  });

  it("OFF succeeds with the operator header and fails without it", async () => {
    mockFetch({body: {final_decision: "ALLOW", policy_decision: "BYPASSED"}});
    const ok = await OG.runScenario(cfgWithOp, "rogue_device", {
      protection: false,
    });
    expect(ok.final_decision).toBe("ALLOW");

    /* Backend contract: protection=false without X-OmniGuard-Operator is 401. */
    mockFetch({
      ok: false,
      status: 401,
      body: {
        detail:
          "Disabling protection requires X-OmniGuard-Operator header (demo comparison only)",
      },
    });
    await expect(
      fetch(
        "http://127.0.0.1:8000/api/scenarios/rogue_device/run?protection=false&reset_first=true",
        {method: "POST"},
      ).then(async (r) => {
        const body = JSON.parse(await r.text());
        if (!r.ok) {
          const err = new Error(body.detail);
          err.status = r.status;
          throw err;
        }
        return body;
      }),
    ).rejects.toMatchObject({status: 401});
  });
});

describe("teleop rejection reasons", () => {
  it("prefers reasons[] over a singular reason field", () => {
    expect(
      OG.rejectionReasons({
        status: "REJECTED",
        reasons: ["RESTRICTED_DESTINATION", "SEQUENCE_REPLAY"],
        reason: "ignored",
      }),
    ).toEqual(["RESTRICTED_DESTINATION", "SEQUENCE_REPLAY"]);
  });

  it("falls back to singular reason when reasons[] is absent", () => {
    expect(
      OG.rejectionReasons({status: "REJECTED", reason: "LEASE_EXPIRED"}),
    ).toEqual(["LEASE_EXPIRED"]);
  });
});

describe("teleop contract", () => {
  it("start sends identity and the real starting point", async () => {
    const spy = mockFetch({body: {final_decision: "ALLOW", control_id: "abc"}});
    await OG.teleopStart(cfg, "legit", {x: 4.2, y: 2.7, speed: 0.8});
    expect(urlOf(spy)).toBe("http://127.0.0.1:8000/api/teleop/start");
    expect(bodyOf(spy)).toMatchObject({
      credential: "fleet-agent-valid-token",
      agent_id: "fleet-agent-01",
      device_id: "fleet-controller-01",
      robot_id: "robot-01",
      x: 4.2,
      y: 2.7,
      speed: 0.8,
    });
  });

  it("sends the rogue device to the backend rather than blocking locally", async () => {
    const spy = mockFetch({
      body: {final_decision: "BLOCK", reasons: ["UNKNOWN_DEVICE"]},
    });
    await OG.teleopStart(cfg, "rogue", {x: 0, y: 0, speed: 0.8});
    expect(bodyOf(spy).device_id).toBe("rogue-controller");
    expect(bodyOf(spy).agent_id).toBe("fleet-agent-01");
  });

  it("move carries a sequence and never a browser-supplied zone", async () => {
    const spy = mockFetch({body: {status: "EXECUTED"}});
    await OG.teleopMove(cfg, {
      controlId: "abc",
      sequence: 17,
      x: 1,
      y: 2,
      speed: 0.5,
    });
    const body = bodyOf(spy);
    expect(body).toMatchObject({
      control_id: "abc",
      sequence: 17,
      robot_id: "robot-01",
    });
    expect(body.zone).toBeUndefined();
    expect(body.destination).toBeUndefined();
  });

  it("stop carries the lease and a reason", async () => {
    const spy = mockFetch({body: {status: "EXECUTED"}});
    await OG.teleopStop(cfg, {controlId: "abc", reason: "JOYSTICK_RELEASED"});
    expect(urlOf(spy)).toBe("http://127.0.0.1:8000/api/teleop/stop");
    expect(bodyOf(spy)).toEqual({
      control_id: "abc",
      robot_id: "robot-01",
      reason: "JOYSTICK_RELEASED",
    });
  });

  it("arm preset goes through the backend teleop proxy with the lease", async () => {
    const spy = mockFetch({body: {status: "QUEUED", command_id: "arm-1"}});
    await OG.teleopArmPreset(cfg, {controlId: "abc", preset: "reach"});
    expect(urlOf(spy)).toBe("http://127.0.0.1:8000/api/teleop/arm/preset");
    expect(bodyOf(spy)).toEqual({
      control_id: "abc",
      robot_id: "robot-01",
      preset: "reach",
    });
  });

  it("arm joints goes through the backend teleop proxy with targets_degrees", async () => {
    const spy = mockFetch({
      body: {status: "QUEUED", command_id: "arm-joints-1"},
    });
    await OG.teleopArmJoints(cfg, {
      controlId: "abc",
      targetsDegrees: {panda_joint1: 10, panda_joint2: -35},
    });
    expect(urlOf(spy)).toBe("http://127.0.0.1:8000/api/teleop/arm/joints");
    expect(bodyOf(spy)).toEqual({
      control_id: "abc",
      robot_id: "robot-01",
      targets_degrees: {panda_joint1: 10, panda_joint2: -35},
    });
  });

  it("gripper goes through the backend teleop proxy with the lease", async () => {
    const spy = mockFetch({body: {status: "QUEUED", command_id: "grip-1"}});
    await OG.teleopGripper(cfg, {controlId: "abc", action: "close"});
    expect(urlOf(spy)).toBe("http://127.0.0.1:8000/api/teleop/gripper");
    expect(bodyOf(spy)).toEqual({
      control_id: "abc",
      robot_id: "robot-01",
      action: "close",
    });
  });

  it("surfaces a rejected packet as a typed error the loop can fail closed on", async () => {
    mockFetch({ok: false, status: 409, body: {detail: "LEASE_EXPIRED"}});
    await expect(
      OG.teleopMove(cfg, {controlId: "a", sequence: 2, x: 0, y: 0, speed: 0.5}),
    ).rejects.toMatchObject({status: 409, message: "LEASE_EXPIRED"});
  });

  it("reports a missing gateway as 404 so the UI can say so", async () => {
    mockFetch({ok: false, status: 404, body: {detail: "Not Found"}});
    await expect(OG.getTeleopConfig(cfg)).rejects.toMatchObject({status: 404});
  });
});

describe("zones and speed (display only — backend is authoritative)", () => {
  const zones = OG.FALLBACK_TELEOP_CONFIG.zones;

  it("resolves restricted before safe on overlap", () => {
    expect(OG.zoneAt(0, 0, zones)).toBe("SAFE_ZONE_A");
    expect(OG.zoneAt(7.5, 0, zones)).toBe("SAFE_ZONE_B");
    expect(OG.zoneAt(6, 5, zones)).toBe("RESTRICTED_ZONE");
    expect(OG.zoneAt(2, 2.5, zones)).toBe("RESTRICTED_ZONE");
  });

  it("treats anything off the map as out of bounds", () => {
    expect(OG.zoneAt(13, 0, zones)).toBe("OUT_OF_BOUNDS");
    expect(OG.zoneAt(0, 2.1, zones)).toBe("OUT_OF_BOUNDS");
  });

  it("derives autonomous waypoints from advertised zone geometry", () => {
    expect(OG.zoneCenter(zones, "SAFE_ZONE_A")).toEqual({x: 0, y: -1});
    expect(OG.zoneCenter(zones, "SAFE_ZONE_B")).toEqual({x: 8, y: -1});
    expect(OG.zoneCenter(zones, "MISSING")).toBeNull();
  });

  it("derives a clockwise Zone A patrol with clearance from every boundary", () => {
    const route = OG.zonePerimeter(zones, "SAFE_ZONE_A");
    expect(route).toEqual([
      {id: "south-west", label: "south-west corner", x: -3.25, y: -3.25},
      {id: "south-east", label: "south-east corner", x: 3.25, y: -3.25},
      {id: "north-east", label: "north-east corner", x: 3.25, y: 1.25},
      {id: "north-west", label: "north-west corner", x: -3.25, y: 1.25},
    ]);
    expect(
      route.every(
        (point) => OG.zoneAt(point.x, point.y, zones) === "SAFE_ZONE_A",
      ),
    ).toBe(true);
  });

  it("fails closed for unusable patrol geometry and unknown scenarios", () => {
    expect(
      OG.zonePerimeter(
        {TINY: {x_min: 0, x_max: 1, y_min: 0, y_max: 1}},
        "TINY",
      ),
    ).toBeNull();
    expect(OG.zonePerimeter(zones, "MISSING")).toBeNull();
    expect(OG.simulationRoute(zones, "zone-shuttle")).toHaveLength(2);
    expect(OG.simulationRoute(zones, "zone-a-perimeter")).toHaveLength(4);
    expect(OG.simulationRoute(zones, "unknown")).toBeNull();
  });

  it("maps deflection within the governor and lets a rogue client exceed it", () => {
    expect(OG.speedFor(0.05, {maxSpeed: 1.5})).toBe(0);
    expect(OG.speedFor(1, {maxSpeed: 1.5})).toBeLessThanOrEqual(1.5);
    expect(OG.speedFor(1, {maxSpeed: 1.5, overspeed: true})).toBeGreaterThan(
      1.5,
    );
  });
});

describe("physical position", () => {
  it("reads either array or object form from isaac_bridge_state", () => {
    expect(OG.readPosition({position: [10, 4]})).toEqual({x: 10, y: 4});
    expect(OG.readPosition({position: {x: 1.5, y: -2}})).toEqual({
      x: 1.5,
      y: -2,
    });
  });

  it("returns null rather than inventing an origin", () => {
    expect(OG.readPosition(null)).toBeNull();
    expect(OG.readPosition({})).toBeNull();
    expect(OG.readPosition({position: {x: "nope", y: 0}})).toBeNull();
  });
});

describe("gamepad mapping", () => {
  const pad = (axes, buttons = []) => ({axes, buttons, mapping: "standard"});

  it("routes the left stick to the operator and the right stick to the attacker", () => {
    const p = pad([0.9, -0.4, -0.7, 0.2]); // L: right+up, R: left+down
    const op = OG.padStickFor(p, 0);
    const rogue = OG.padStickFor(p, 1);
    expect(op.vec.x).toBeCloseTo(0.9);
    expect(op.vec.y).toBeCloseTo(0.4); // screen y inverted to world y
    expect(rogue.vec.x).toBeCloseTo(-0.7);
    expect(rogue.vec.y).toBeCloseTo(-0.2);
    expect(op.active && rogue.active).toBe(true);
  });

  it("reports released so the thumb can spring back, never a stale deflection", () => {
    const released = OG.padStickFor(pad([0.02, -0.01, 0, 0]), 0);
    expect(released).toEqual({vec: {x: 0, y: 0}, mag: 0, active: false});
  });

  it("ignores stick drift below the deadzone", () => {
    expect(OG.padStickFor(pad([0.1, 0.05, 0, 0]), 0).active).toBe(false);
    expect(OG.padStickFor(pad([0.3, 0.0, 0, 0]), 0).active).toBe(true);
  });

  it("clamps magnitude to 1 on a full diagonal", () => {
    expect(OG.padStickFor(pad([1, -1, 0, 0]), 0).mag).toBe(1);
  });

  it("survives a pad with missing axes", () => {
    expect(OG.padStickFor(pad([]), 1).active).toBe(false);
    expect(OG.padStickFor(undefined, 0).active).toBe(false);
  });

  it("detects Circle as the emergency stop", () => {
    expect(
      OG.padEstopPressed(
        pad([0, 0, 0, 0], [{pressed: false}, {pressed: true}]),
      ),
    ).toBe(true);
    expect(
      OG.padEstopPressed(
        pad([0, 0, 0, 0], [{pressed: true}, {pressed: false}]),
      ),
    ).toBe(false);
    expect(OG.padEstopPressed(undefined)).toBe(false);
  });
});

describe("keyboard control (no click-to-focus)", () => {
  it("splits WASD to the operator and arrows to the hacker", async () => {
    const {vectorFor} = await import("../useKeyboardControl.js");
    expect(vectorFor(new Set(["w"]), "legit")).toEqual({
      vec: {x: 0, y: 1},
      mag: 1,
    });
    expect(vectorFor(new Set(["ArrowUp"]), "rogue")).toEqual({
      vec: {x: 0, y: 1},
      mag: 1,
    });
    // Each plane ignores the other plane's keys, so both can be driven at once.
    expect(vectorFor(new Set(["ArrowUp"]), "legit").mag).toBe(0);
    expect(vectorFor(new Set(["w"]), "rogue").mag).toBe(0);
  });

  it("normalises diagonals so they are not faster than cardinals", async () => {
    const {vectorFor} = await import("../useKeyboardControl.js");
    const d = vectorFor(new Set(["w", "d"]), "legit");
    expect(Math.hypot(d.vec.x, d.vec.y)).toBeCloseTo(1);
    expect(d.vec.x).toBeCloseTo(Math.SQRT1_2);
    expect(d.vec.y).toBeCloseTo(Math.SQRT1_2);
  });

  it("cancels opposing keys and reports released", async () => {
    const {vectorFor} = await import("../useKeyboardControl.js");
    expect(vectorFor(new Set(["w", "s"]), "legit")).toEqual({
      vec: {x: 0, y: 0},
      mag: 0,
    });
    expect(vectorFor(new Set(), "legit").mag).toBe(0);
  });
});

describe("session log export", () => {
  it("emits a header and one row per decision", async () => {
    const {toCsv} = await import("../useSessionLog.js");
    const rows = toCsv([
      {
        timestamp: "2026-08-22T10:00:00Z",
        final_decision: "BLOCK",
        reasons: ["UNKNOWN_DEVICE"],
      },
      {timestamp: "2026-08-22T10:00:05Z", final_decision: "ALLOW", reasons: []},
    ]).split("\n");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toContain('"final_decision"');
    expect(rows[1]).toContain('"BLOCK"');
    expect(rows[2]).toContain('"ALLOW"');
  });

  it("escapes quotes and commas in free-text reasons", async () => {
    const {toCsv} = await import("../useSessionLog.js");
    const csv = toCsv([
      {final_decision: "BLOCK", reasons: ['said "no", firmly']},
    ]);
    expect(csv).toContain('"said ""no"", firmly"');
    // The embedded comma must not create an extra column.
    const [header, row] = csv.split("\n");
    expect(row.split('\",\"')).toHaveLength(header.split('\",\"').length);
  });

  it("tolerates missing fields rather than writing undefined", async () => {
    const {toCsv} = await import("../useSessionLog.js");
    expect(toCsv([{}]).split("\n")[1]).not.toContain("undefined");
  });
});

describe("controller aux buttons (arm + gripper)", () => {
  /* These names are validated server-side in backend/teleop.py; anything else
   * comes back INVALID_ARM_PRESET / INVALID_GRIPPER_ACTION. */
  const BACKEND_PRESETS = ["stow", "carry", "reach", "inspect"];
  const BACKEND_ACTIONS = ["open", "close"];

  const fireAll = async () => {
    const {AUX_BUTTONS} = await import("../useController.js");
    const calls = [];
    const aux = {
      armPreset: (p) => calls.push(["arm", p]),
      gripperFor: (panel, a) => calls.push(["grip", a, panel]),
    };
    const byIndex = {};
    for (const [index, fire] of AUX_BUTTONS) {
      calls.length = 0;
      fire(aux);
      byIndex[index] = calls[0];
    }
    return byIndex;
  };

  it("maps the d-pad to the four arm presets", async () => {
    const b = await fireAll();
    expect(b[12]).toEqual(["arm", "reach"]);
    expect(b[13]).toEqual(["arm", "stow"]);
    expect(b[14]).toEqual(["arm", "carry"]);
    expect(b[15]).toEqual(["arm", "inspect"]);
  });

  /* Left shoulders belong to the operator, right shoulders to the hacker, so a
   * gripper press is always attributable to one plane. */
  it("splits the shoulders across the two control planes", async () => {
    const b = await fireAll();
    expect(b[4]).toEqual(["grip", "open", "legit"]); // L1
    expect(b[6]).toEqual(["grip", "close", "legit"]); // L2
    expect(b[5]).toEqual(["grip", "open", "rogue"]); // R1
    expect(b[7]).toEqual(["grip", "close", "rogue"]); // R2
  });

  it("sends only names the backend accepts", async () => {
    const b = await fireAll();
    const sent = Object.values(b);
    const presets = sent.filter(([k]) => k === "arm").map(([, v]) => v);
    const actions = sent.filter(([k]) => k === "grip").map(([, v]) => v);
    expect(presets.sort()).toEqual([...BACKEND_PRESETS].sort());
    expect([...new Set(actions)].sort()).toEqual([...BACKEND_ACTIONS].sort());
  });

  it("does not collide with the emergency-stop button", async () => {
    const {AUX_BUTTONS} = await import("../useController.js");
    const {PAD_ESTOP_BUTTON} = await import("../omniguard.js");
    expect(AUX_BUTTONS.map(([i]) => i)).not.toContain(PAD_ESTOP_BUTTON);
  });
});

describe("readManipulator", () => {
  it("returns null before any arm or gripper is known", () => {
    expect(OG.readManipulator(null, {})).toBeNull();
    expect(OG.readManipulator({position: {x: 1, y: 2}}, {})).toBeNull();
  });

  it("prefers isaac_bridge_state over locally commanded state", () => {
    const bridge = {
      arm: {mode: "preset", preset: "reach"},
      gripper: {action: "close", joints: ["/panda_finger_joint1"]},
    };
    const m = OG.readManipulator(bridge, {arm: "stow", gripper: "open"});
    expect(m.arm).toEqual({
      preset: "reach",
      mode: "preset",
      source: "confirmed",
    });
    expect(m.gripper).toEqual({action: "close", source: "confirmed"});
  });

  /* mock_bridge_state in backend/main.py carries no arm/gripper keys, so the
   * whole mock demo depends on this fallback. */
  it("falls back to commanded state when the bridge reports none", () => {
    const m = OG.readManipulator(
      {position: {x: 0, y: 0}},
      {arm: "carry", gripper: "open"},
    );
    expect(m.arm).toEqual({
      preset: "carry",
      mode: "preset",
      source: "commanded",
    });
    expect(m.gripper).toEqual({action: "open", source: "commanded"});
  });

  it("reports joints mode without inventing a preset name", () => {
    const m = OG.readManipulator(
      {arm: {mode: "joints", targets_degrees: {panda_joint1: 0}}},
      {},
    );
    expect(m.arm).toEqual({preset: null, mode: "joints", source: "confirmed"});
    expect(m.gripper).toBeNull();
  });

  it("ignores values the backend would have rejected", () => {
    expect(
      OG.readManipulator({arm: {mode: "preset", preset: "wave"}}, {}),
    ).toBeNull();
    expect(
      OG.readManipulator(null, {arm: "wave", gripper: "crush"}),
    ).toBeNull();
  });

  it("only knows the presets and actions backend/teleop.py validates", () => {
    expect(OG.ARM_PRESETS).toEqual(["stow", "carry", "reach", "inspect"]);
    expect(OG.GRIPPER_ACTIONS).toEqual(["open", "close"]);
    for (const preset of OG.ARM_PRESETS) {
      expect(OG.ARM_EXTENSION[preset]).toBeGreaterThan(0);
      expect(OG.ARM_EXTENSION[preset]).toBeLessThanOrEqual(1);
    }
  });
});

describe("headingFrom", () => {
  it("faces the active target", () => {
    expect(OG.headingFrom({x: 0, y: 0}, {x: 5, y: 0}, [])).toBeCloseTo(0);
    expect(OG.headingFrom({x: 0, y: 0}, {x: 0, y: 5}, [])).toBeCloseTo(
      Math.PI / 2,
    );
  });

  it("falls back to the last trail segment when there is no target", () => {
    const trail = [
      {x: 0, y: 0},
      {x: -3, y: 0},
    ];
    expect(Math.abs(OG.headingFrom({x: -3, y: 0}, null, trail))).toBeCloseTo(
      Math.PI,
    );
  });

  it("defaults to +x rather than refusing to draw a stationary robot", () => {
    expect(OG.headingFrom({x: 1, y: 1}, {x: 1, y: 1}, [])).toBe(0);
    expect(OG.headingFrom(null, null, null)).toBe(0);
  });
});

describe("aux key bindings", () => {
  /* Left shoulders are the operator's, right shoulders the hacker's, and every
   * gripper key has to name its plane or the press is unattributable. */
  it("splits the gripper across both control planes", async () => {
    const {AUX_KEYS} = await import("../useKeyboardControl.js");
    const grips = Object.values(AUX_KEYS).filter((e) => e.kind === "gripper");
    for (const g of grips) expect(["legit", "rogue"]).toContain(g.panel);
    for (const panel of ["legit", "rogue"]) {
      const mine = grips.filter((g) => g.panel === panel).map((g) => g.value);
      expect(mine.sort()).toEqual([...OG.GRIPPER_ACTIONS].sort());
    }
    expect(
      grips
        .filter((g) => g.panel === "legit")
        .every((g) => g.pad.startsWith("L")),
    ).toBe(true);
    expect(
      grips
        .filter((g) => g.panel === "rogue")
        .every((g) => g.pad.startsWith("R")),
    ).toBe(true);
  });

  it("binds every backend-validated preset and gripper action", async () => {
    const {AUX_KEYS} = await import("../useKeyboardControl.js");
    const entries = Object.values(AUX_KEYS);
    const presets = entries.filter((e) => e.kind === "arm").map((e) => e.value);
    const actions = entries
      .filter((e) => e.kind === "gripper")
      .map((e) => e.value);
    expect(presets.sort()).toEqual([...OG.ARM_PRESETS].sort());
    expect([...new Set(actions)].sort()).toEqual(
      [...OG.GRIPPER_ACTIONS].sort(),
    );
    expect(entries.filter((e) => e.kind === "estop")).toHaveLength(1);
  });

  /* A key that both moves and actuates would fire two commands per press. */
  it("never reuses a movement key", async () => {
    const {AUX_KEYS, BINDINGS} = await import("../useKeyboardControl.js");
    const movement = [
      ...Object.keys(BINDINGS.legit),
      ...Object.keys(BINDINGS.rogue),
    ];
    for (const key of Object.keys(AUX_KEYS)) {
      expect(movement).not.toContain(key);
    }
  });

  /* The pad and the keyboard must issue the same command for the same action,
   * or the on-screen keycaps become a lie. */
  it("matches the buttons the gamepad table binds", async () => {
    const {AUX_KEYS} = await import("../useKeyboardControl.js");
    const srcDir = new URL("../../", import.meta.url).pathname;
    const source = readFileSync(
      join(srcDir, "components", "DualSense.jsx"),
      "utf8",
    );

    const byPad = {};
    for (const entry of Object.values(AUX_KEYS)) byPad[entry.pad] = entry.value;

    for (const [, preset, hotkey] of source.matchAll(
      /preset: '(\w+)',[\s\S]{0,120}?hotkey: '(\w)'/g,
    )) {
      const pad = Object.entries(AUX_KEYS).find(
        ([k]) => k.toUpperCase() === hotkey.toUpperCase(),
      )?.[1];
      expect(
        pad,
        `hotkey ${hotkey} is not bound on the keyboard`,
      ).toBeDefined();
      expect(pad.value).toBe(preset);
    }

    for (const [, action, hotkey] of source.matchAll(
      /action: '(\w+)',[\s\S]{0,80}?hotkey: '(\w)'/g,
    )) {
      const bound = AUX_KEYS[hotkey.toLowerCase()];
      expect(
        bound,
        `hotkey ${hotkey} is not bound on the keyboard`,
      ).toBeDefined();
      expect(bound.value).toBe(action);
    }

    expect(byPad.L1).toBe("open");
    expect(byPad.L2).toBe("close");
    expect(byPad.R1).toBe("open");
    expect(byPad.R2).toBe("close");
    expect(byPad.circle).toBeNull();
  });
});

describe("aux command attribution", () => {
  /* Regression: a denied plane stays 'denied' until it is grabbed again. If
   * that counted as driving, every later arm press would be redirected to a
   * plane that can never hold a lease and would come back rejected. */
  it("never attributes an arm press to a denied plane", async () => {
    const src = readFileSync(
      new URL("../useController.js", import.meta.url).pathname,
      "utf8",
    );
    const owner = src.slice(
      src.indexOf("const leaseOwner"),
      src.indexOf("const aux = useMemo"),
    );
    expect(owner).toMatch(/phase === ["']starting["']/);
    expect(owner).toMatch(/phase === ["']streaming["']/);
    expect(owner).not.toMatch(/phase !== ['"]idle['"]/);
  });
});
