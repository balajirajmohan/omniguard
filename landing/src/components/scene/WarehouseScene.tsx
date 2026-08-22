import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { box, iso, pt, quad } from './isometric';
import { useReducedMotion } from '../../hooks/useMotionPrefs';
import { Chip, Dot } from '../ui/Primitives';

/**
 * Hero scene: approved and compromised commands alternate through the same
 * gateway, showing both safe forwarding and deterministic containment.
 *
 * The loop is deliberately slow: it is an explanation, not decoration.
 */

type Scenario = 'approved' | 'denied';
type Phase = 'idle' | 'transmit' | 'evaluate' | 'allow' | 'complete' | 'deny' | 'contain';

const SEQUENCE: { scenario: Scenario; phase: Phase; ms: number }[] = [
  { scenario: 'approved', phase: 'idle', ms: 900 },
  { scenario: 'approved', phase: 'transmit', ms: 1400 },
  { scenario: 'approved', phase: 'evaluate', ms: 1200 },
  { scenario: 'approved', phase: 'allow', ms: 1600 },
  { scenario: 'approved', phase: 'complete', ms: 1900 },
  { scenario: 'denied', phase: 'idle', ms: 900 },
  { scenario: 'denied', phase: 'transmit', ms: 1400 },
  { scenario: 'denied', phase: 'evaluate', ms: 1200 },
  { scenario: 'denied', phase: 'deny', ms: 1900 },
  { scenario: 'denied', phase: 'contain', ms: 2600 },
];

const ROBOT = { x: 1.8, y: 5.8 };
const DENIED_ROUTE: [number, number][] = [
  [1.8, 5.8],
  [3.2, 5.1],
  [4.6, 5.5],
  [5.9, 6.0],
];

const APPROVED_ROUTE: [number, number][] = [
  [1.8, 5.8],
  [3.2, 4.8],
  [4.7, 3.2],
  [5.9, 1.8],
];

const CONTAIN_STEPS = ['Credential revoked', 'Identity quarantined', 'Robot E-STOP engaged'];

const DENY_REASONS = ['DEVICE_MISMATCH', 'ZONE_NOT_PERMITTED', 'BEHAVIOR_ANOMALY'];

export function WarehouseScene() {
  const reduced = useReducedMotion();
  const [step, setStep] = useState(0);
  const sequenceStep = reduced
    ? { scenario: 'approved' as const, phase: 'complete' as const, ms: 0 }
    : SEQUENCE[step];
  const { scenario, phase } = sequenceStep;

  useEffect(() => {
    if (reduced) return;
    const t = window.setTimeout(
      () => setStep((s) => (s + 1) % SEQUENCE.length),
      sequenceStep.ms,
    );
    return () => window.clearTimeout(t);
  }, [step, reduced, sequenceStep.ms]);

  const approvedScenario = scenario === 'approved';
  const contained = phase === 'contain';
  const denied = phase === 'deny' || contained;
  const allowed = phase === 'allow' || phase === 'complete';
  const decided = denied || allowed;
  const routeActive = phase === 'transmit' || phase === 'evaluate' || allowed;

  const racksA = box(0.6, 3.55, 3.2, 4.15, 30);
  const racksB = box(4.8, 3.55, 7.4, 4.15, 30);
  const robotBody = box(ROBOT.x, ROBOT.y, ROBOT.x + 0.62, ROBOT.y + 0.62, 15);

  const activeRoute = approvedScenario ? APPROVED_ROUTE : DENIED_ROUTE;
  const routePath = activeRoute
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${pt(x, y, 3)}`)
    .join(' ');
  const [humanX, humanY] = iso(6.5, 6.5, 6);

  return (
    <div className="relative w-full" role="img" aria-label={SCENE_DESCRIPTION}>
      <div className="relative aspect-[660/560] w-full">
        <svg
          viewBox="0 0 660 560"
          className="absolute inset-0 h-full w-full"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="og-floor" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#101a26" />
              <stop offset="100%" stopColor="#080d14" />
            </linearGradient>
            <linearGradient id="og-gate" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.05" />
              <stop offset="50%" stopColor="#22d3ee" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.05" />
            </linearGradient>
            <linearGradient id="og-rack" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1d2a3a" />
              <stop offset="100%" stopColor="#121a25" />
            </linearGradient>
            <radialGradient id="og-glow" cx="50%" cy="50%">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="og-glow-red" cx="50%" cy="50%">
              <stop offset="0%" stopColor="#ff5533" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#ff5533" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* ---------- Command link: controller → gateway → robot ---------- */}
          <g>
            <line
              x1="96"
              y1="96"
              x2="292"
              y2="96"
              stroke="#22d3ee"
              strokeOpacity="0.28"
              strokeWidth="1.25"
              strokeDasharray="4 5"
            />
            <line
              x1="368"
              y1="96"
              x2="566"
              y2="96"
              stroke={allowed ? '#34d399' : '#2a3849'}
              strokeOpacity={allowed ? 0.42 : 0.3}
              strokeWidth="1.25"
              strokeDasharray="4 5"
            />

            {/* Controller node */}
            <rect
              x="44"
              y="78"
              width="52"
              height="36"
              rx="5"
              fill="#101724"
              stroke="#2a3849"
              strokeWidth="1.2"
            />
            <rect x="54" y="88" width="32" height="3" rx="1.5" fill="#22d3ee" fillOpacity="0.5" />
            <rect x="54" y="95" width="22" height="3" rx="1.5" fill="#6b7f96" fillOpacity="0.6" />
            <rect x="54" y="102" width="27" height="3" rx="1.5" fill="#6b7f96" fillOpacity="0.4" />

            {/* Robot-side endpoint */}
            <rect
              x="566"
              y="80"
              width="46"
              height="32"
              rx="5"
              fill="#101724"
              stroke={contained ? '#ff5533' : '#2a3849'}
              strokeWidth="1.2"
            />
            <circle cx="589" cy="96" r="4.5" fill={contained ? '#ff5533' : '#34d399'} />

            {/* Gateway plane: the checkpoint every command crosses. */}
            <polygon
              points="300,26 360,44 360,166 300,148"
              fill="url(#og-gate)"
              stroke={denied ? '#ff5533' : '#22d3ee'}
              strokeOpacity={denied ? 0.75 : 0.5}
              strokeWidth="1.3"
            />
            <line
              x1="330"
              y1="35"
              x2="330"
              y2="157"
              stroke={denied ? '#ff5533' : '#22d3ee'}
              strokeOpacity="0.35"
              strokeWidth="1"
              strokeDasharray="3 4"
            />
            {phase === 'evaluate' && !reduced && (
              <rect
                x="300"
                y="26"
                width="60"
                height="18"
                fill="#22d3ee"
                fillOpacity="0.35"
                style={{ animation: 'og-scan 1.5s linear infinite' }}
              />
            )}

            {/* Command packet: blocked at the gateway, never reaching the robot. */}
            <AnimatePresence mode="wait">
              {phase !== 'idle' && (
                <motion.g
                  key={`${scenario}-command-packet`}
                  initial={{ x: 0, opacity: 0 }}
                  animate={{
                    x: allowed ? 493 : 234,
                    opacity: contained ? 0 : 1,
                  }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: reduced ? 0 : 1.5, ease: [0.4, 0, 0.2, 1] }}
                >
                  <circle cx="96" cy="96" r="14" fill="url(#og-glow)" />
                  <circle
                    cx="96"
                    cy="96"
                    r="5"
                    fill={denied ? '#ff5533' : '#22d3ee'}
                    stroke="#070a0f"
                    strokeWidth="1.5"
                  />
                </motion.g>
              )}
            </AnimatePresence>
          </g>

          {/* ---------- Warehouse floor ---------- */}
          <g>
            <polygon points={quad(0, 0, 8, 8)} fill="url(#og-floor)" />

            {/* Floor grid */}
            <g stroke="#22d3ee" strokeOpacity="0.09" strokeWidth="0.8">
              {Array.from({ length: 9 }, (_, i) => (
                <line key={`gx${i}`} {...lineProps(i, 0, i, 8)} />
              ))}
              {Array.from({ length: 9 }, (_, i) => (
                <line key={`gy${i}`} {...lineProps(0, i, 8, i)} />
              ))}
            </g>

            {/* Zone overlays */}
            <polygon
              points={quad(0.6, 0.6, 3.2, 3.2)}
              fill="#22d3ee"
              fillOpacity="0.05"
              stroke="#22d3ee"
              strokeOpacity="0.3"
              strokeWidth="1"
            />
            <polygon
              points={quad(4.8, 0.6, 7.4, 3.2)}
              fill="#22d3ee"
              fillOpacity="0.05"
              stroke="#22d3ee"
              strokeOpacity="0.3"
              strokeWidth="1"
            />
            <polygon
              points={quad(4.4, 4.6, 7.4, 7.4)}
              fill="#ff5533"
              fillOpacity={denied ? 0.14 : 0.08}
              stroke="#ff5533"
              strokeOpacity={denied ? 0.7 : 0.42}
              strokeWidth="1.2"
              strokeDasharray="6 4"
            />

            {/* Storage racks */}
            {[racksA, racksB].map((r, i) => (
              <g key={i}>
                <polygon points={r.left} fill="#0f1720" stroke="#243040" strokeWidth="0.8" />
                <polygon points={r.right} fill="#151f2c" stroke="#243040" strokeWidth="0.8" />
                <polygon points={r.top} fill="url(#og-rack)" stroke="#2a3849" strokeWidth="0.9" />
              </g>
            ))}

            {/* Planned route */}
            <path
              d={routePath}
              fill="none"
              stroke={denied ? '#ff5533' : allowed ? '#34d399' : '#22d3ee'}
              strokeOpacity={denied ? 0.5 : 0.75}
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={denied ? '3 7' : '10 8'}
              style={
                routeActive && !reduced
                  ? { animation: 'og-dash 3s linear infinite' }
                  : undefined
              }
            />
            {/* Destination marker inside the human zone */}
            <circle
              cx={iso(5.9, 6.0, 3)[0]}
              cy={iso(5.9, 6.0, 3)[1]}
              r="4"
              fill={denied ? '#ff5533' : allowed ? '#34d399' : '#22d3ee'}
            />

            {/* Human silhouette */}
            <g transform={`translate(${humanX - 5}, ${humanY - 30})`}>
              <circle cx="5" cy="5" r="4.2" fill="#ff8a6b" />
              <path
                d="M5 10.5c-3.4 0-5 2.2-5 5.6v6.2h10v-6.2c0-3.4-1.6-5.6-5-5.6Z"
                fill="#ff8a6b"
              />
              <path d="M2.4 22.3 1 30M7.6 22.3 9 30" stroke="#ff8a6b" strokeWidth="2.2" strokeLinecap="round" />
            </g>

            {/* Robot */}
            <g>
              {contained && (
                <ellipse
                  cx={iso(ROBOT.x + 0.31, ROBOT.y + 0.31)[0]}
                  cy={iso(ROBOT.x + 0.31, ROBOT.y + 0.31)[1]}
                  rx="58"
                  ry="30"
                  fill="url(#og-glow-red)"
                />
              )}
              <polygon points={robotBody.left} fill="#12202c" stroke="#2a3849" strokeWidth="0.8" />
              <polygon points={robotBody.right} fill="#182a38" stroke="#2a3849" strokeWidth="0.8" />
              <polygon
                points={robotBody.top}
                fill={contained ? '#3a1a16' : '#1d3242'}
                stroke={contained ? '#ff5533' : '#22d3ee'}
                strokeWidth="1.2"
              />
              <circle
                cx={iso(ROBOT.x + 0.31, ROBOT.y + 0.31, 15)[0]}
                cy={iso(ROBOT.x + 0.31, ROBOT.y + 0.31, 15)[1]}
                r="3.4"
                fill={contained ? '#ff5533' : '#34d399'}
                style={
                  contained && !reduced
                    ? { animation: 'og-blink 1.4s ease-in-out 3' }
                    : undefined
                }
              />
            </g>
          </g>

          {/* Drifting particles create a faint sense of a live volume. */}
          {!reduced && (
            <g fill="#22d3ee" fillOpacity="0.3">
              {PARTICLES.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={p.r}
                  style={{
                    animation: `og-drift ${p.d}s ease-in-out ${p.delay}s infinite alternate`,
                  }}
                />
              ))}
            </g>
          )}
        </svg>

        {/* ---------- Readable HTML overlays ---------- */}
        <SceneLabel className="left-[6%] top-[11%]">CONTROL PLANE</SceneLabel>
        <SceneLabel className="right-[3%] top-[11%]" tone={contained ? 'deny' : 'neutral'}>
          ROBOT
        </SceneLabel>
        <SceneLabel className="left-[22%] top-[41%]">ZONE_A</SceneLabel>
        <SceneLabel className="right-[16%] top-[41%]">ZONE_B</SceneLabel>
        <SceneLabel className="right-[8%] bottom-[26%]" tone="deny">
          HUMAN_ZONE
        </SceneLabel>

        {/* Gateway caption */}
        <div className="pointer-events-none absolute left-1/2 top-[2%] -translate-x-1/2 text-center">
          <p className="font-mono text-[10px] tracking-[0.16em] text-cyan/70">OMNIGUARD GATEWAY</p>
        </div>

        {/* Travelling command label */}
        <AnimatePresence>
          {(phase === 'transmit' || phase === 'evaluate') && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              className="pointer-events-none absolute left-1/2 top-[29%] -translate-x-1/2"
            >
              <span className="whitespace-nowrap rounded border border-cyan/40 bg-graphite/90 px-2.5 py-1.5 font-mono text-[10.5px] text-cyan-bright sm:text-[11.5px]">
                {approvedScenario ? 'MOVE → ZONE_B • 0.8 m/s' : 'MOVE → HUMAN_ZONE • 1.8 m/s'}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Decision card */}
        <AnimatePresence>
          {decided && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: reduced ? 0 : 0.4, ease: [0.22, 1, 0.36, 1] }}
              className={`absolute left-1/2 top-[24%] w-[62%] max-w-[268px] -translate-x-1/2 rounded-lg border bg-graphite/94 p-3.5 backdrop-blur-sm sm:w-[54%] ${
                denied
                  ? 'border-deny/55 shadow-[0_20px_60px_-20px_rgba(255,85,51,0.5)]'
                  : 'border-allow/55 shadow-[0_20px_60px_-20px_rgba(52,211,153,0.35)]'
              }`}
            >
              <div className="flex items-center gap-2">
                <Dot tone={denied ? 'deny' : 'allow'} pulse={(contained || allowed) && !reduced} />
                <span
                  className={`font-mono text-[13px] font-semibold tracking-[0.1em] ${
                    denied ? 'text-deny' : 'text-allow'
                  }`}
                >
                  {denied ? 'DENIED' : 'APPROVED'}
                </span>
                <span className="ml-auto font-mono text-[10px] text-ink-faint">
                  {denied ? '42 ms' : '31 ms'}
                </span>
              </div>
              {denied ? (
                <ul className="mt-2.5 space-y-1">
                  {DENY_REASONS.map((r) => (
                    <li key={r} className="font-mono text-[10.5px] leading-tight text-ink-dim">
                      <span className="text-deny/80">•</span> {r}
                    </li>
                  ))}
                </ul>
              ) : (
                <ul className="mt-2.5 space-y-1">
                  {['IDENTITY_VERIFIED', 'ZONE_PERMITTED', 'PATH_CLEAR'].map((reason) => (
                    <li key={reason} className="flex items-center gap-1.5 font-mono text-[10.5px] text-ink-dim">
                      <AllowCheckIcon />
                      {reason}
                    </li>
                  ))}
                </ul>
              )}
              <AnimatePresence>
                {contained && (
                  <motion.ul
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: reduced ? 0 : 0.35 }}
                    className="mt-2.5 space-y-1 overflow-hidden border-t border-hairline pt-2.5"
                  >
                    {CONTAIN_STEPS.map((c, i) => (
                      <motion.li
                        key={c}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: reduced ? 0 : 0.25 + i * 0.35, duration: 0.3 }}
                        className="flex items-center gap-1.5 font-mono text-[10.5px] text-ink"
                      >
                        <CheckIcon />
                        {c}
                      </motion.li>
                    ))}
                  </motion.ul>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ---------- Status rail ---------- */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Chip tone={denied ? 'deny' : allowed ? 'allow' : 'cyan'}>
          {denied ? 'Command denied in 42 ms' : allowed ? 'Command approved in 31 ms' : 'Evaluating command'}
        </Chip>
        <Chip>Policy v1.4</Chip>
        <Chip tone={denied ? 'deny' : allowed ? 'allow' : 'neutral'}>
          AI risk {approvedScenario ? '0.08' : '0.96'}
        </Chip>
        <Chip tone={contained ? 'deny' : allowed ? 'allow' : 'neutral'}>
          {contained ? 'Robot contained' : allowed ? 'Robot moving' : 'Robot active'}
        </Chip>
      </div>
      <p className="mt-2.5 font-mono text-[10.5px] leading-relaxed text-ink-faint">
        Illustrative demo telemetry. Values shown are from a scripted scenario.
      </p>
    </div>
  );
}

const SCENE_DESCRIPTION =
  'Animated isometric warehouse digital twin showing commands from the control plane to the robot, ' +
  'alternating between an approved move to ZONE_B and ' +
  'a denied move into HUMAN_ZONE. Every command is evaluated by the OmniGuard gateway before the ' +
  'robot moves; unsafe commands trigger credential revocation, quarantine and emergency stop.';

const PARTICLES = [
  { x: 150, y: 300, r: 1.2, d: 7, delay: 0 },
  { x: 470, y: 250, r: 1, d: 9, delay: 1.2 },
  { x: 250, y: 430, r: 1.4, d: 8, delay: 0.6 },
  { x: 540, y: 400, r: 1, d: 10, delay: 2 },
  { x: 380, y: 200, r: 0.9, d: 6, delay: 1.6 },
  { x: 110, y: 380, r: 1.1, d: 11, delay: 0.3 },
];

function lineProps(x0: number, y0: number, x1: number, y1: number) {
  const [a, b] = iso(x0, y0);
  const [c, d] = iso(x1, y1);
  return { x1: a, y1: b, x2: c, y2: d };
}

function SceneLabel({
  children,
  className = '',
  tone = 'neutral',
}: {
  children: string;
  className?: string;
  tone?: 'neutral' | 'deny';
}) {
  return (
    <span
      className={`pointer-events-none absolute font-mono text-[9.5px] tracking-[0.12em] sm:text-[10.5px] ${
        tone === 'deny' ? 'text-deny/85' : 'text-ink-faint'
      } ${className}`}
    >
      {children}
    </span>
  );
}

function CheckIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path
        d="M2 6.4 4.7 9 10 3.2"
        stroke="#ff5533"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AllowCheckIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path
        d="M2 6.4 4.7 9 10 3.2"
        stroke="#34d399"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
