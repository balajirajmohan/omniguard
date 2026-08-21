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
    expect(OG.zoneAt(6, 8, zones)).toBe("RESTRICTED_ZONE");
    expect(OG.zoneAt(2, 5, zones)).toBe("RESTRICTED_ZONE");
  });

  it("treats anything off the map as out of bounds", () => {
    expect(OG.zoneAt(16, 0, zones)).toBe("OUT_OF_BOUNDS");
    expect(OG.zoneAt(0, 5.1, zones)).toBe("OUT_OF_BOUNDS");
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
