# OmniGuard — Zero Trust for Physical AI

Marketing site + operations-console demo for OmniGuard, the runtime security and governance
control plane for autonomous robots and physical AI systems.

React 19 · TypeScript · Vite · Tailwind CSS v4 · Framer Motion

## Run

```bash
npm install
npm run dev      # http://localhost:5174
npm run build    # typecheck + production bundle to dist/
npm run preview
```

## Routes

| Route   | Contents |
| ------- | -------- |
| `/`     | Landing page — hero warehouse twin, problem sequence, three-layer model, interactive Decision Lab, Omniverse section, architecture, use cases, comparison, adoption, final CTA. |
| `/demo` | Full-screen operations console — left nav, system status rail, warehouse map, current command, policy trace, AI anomaly meter, incident timeline, containment panel, scenario buttons, Reset Demo. |

Both routes are client-rendered. When deploying, configure an SPA history fallback so `/demo`
serves `index.html` (Netlify `_redirects`, Vercel rewrites, or `try_files` on nginx).

## Wiring a real backend

All illustrative telemetry lives in **`src/data/demoData.ts`** and every endpoint in
**`src/config/endpoints.ts`**. No component contains hardcoded data or URLs.

Set an API base to switch the UI from "Interactive product preview" to live labelling:

```bash
cp .env.example .env.local
# VITE_OMNIGUARD_API_BASE=https://omniguard.internal
# VITE_OMNIGUARD_CONSOLE_URL=http://localhost:5173
```

Expected endpoints:

- `GET /health` — broker, model, simulator, audit-chain readiness (top status rail)
- `POST /api/commands` — submit a command and receive a decision trace
- `GET /api/incidents` — durable containment history
- `GET /api/scenarios` — available backend scenarios
- `GET /api/state` — current system and robot state

To stream real decisions, replace the timer inside `src/components/decision/useScenarioRun.ts`
with the `POST /command` response. Every consumer reads the same `revealed` / `settled` /
`complete` contract, so no UI changes are needed.

## Structure

```
src/
  components/
    decision/   DecisionTrace, RiskMeter, Verdict, FieldTable, ScenarioPicker, useScenarioRun
    scene/      isometric projection helpers, WarehouseScene (hero), TwinMap (console)
    ui/         Button, Reveal, Primitives (Chip, Dot, Section, SectionHeading, Panel)
    Nav, Footer, Logo
  sections/     One file per landing-page section
  pages/        Landing, Demo
  data/         demoData.ts — the single swap point for real API data
  config/       endpoints.ts — the single swap point for URLs
  index.css     Design tokens (@theme), base layer, keyframes
```

## Design notes

- **Colour carries state.** Cyan = system/accent, emerald = allowed, amber = constrained,
  red-orange = denied or contained. Every status is also conveyed by text, never colour alone.
- **Hard policy and AI evidence are always reported separately** — the risk meter shows the 0.80
  threshold, and copy states that AI can add risk evidence but never override a safety policy.
- **Motion is explanatory.** The hero loop runs slowly enough to read; `prefers-reduced-motion`
  collapses animation to its final frame rather than shortening it, and the decision trace reveals
  in full so no information depends on motion.
- All figures shown are scripted demo telemetry and labelled as such.

## Status

Hackathon prototype — not certified for production safety use.
