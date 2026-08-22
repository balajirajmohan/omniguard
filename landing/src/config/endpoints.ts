/**
 * Single source of truth for backend wiring.
 *
 * The UI ships with local mock data (see `src/data/demoData.ts`). When
 * `VITE_OMNIGUARD_API_BASE` is set, the same components can fetch live
 * decisions without any redesign; only the data source changes.
 */

const base = (import.meta.env.VITE_OMNIGUARD_API_BASE ?? '').replace(/\/$/, '');

export const endpoints = {
  base,
  /** Broker / model / simulator readiness. */
  health: `${base}/health`,
  /** Submit a command for authorization; returns a decision trace. */
  command: `${base}/api/commands`,
  /** Historical containment events. */
  incidents: `${base}/api/incidents`,
  scenarios: `${base}/api/scenarios`,
  state: `${base}/api/state`,
  reset: `${base}/api/reset`,
} as const;

/** Local interactive product preview. */
export const PREVIEW_ROUTE = '/demo';

/** Real operations console, deployed independently from the landing site. */
export const OPERATIONS_CONSOLE_URL =
  import.meta.env.VITE_OMNIGUARD_CONSOLE_URL ?? 'http://localhost:5173';

/** False until a backend is configured; drives the "product preview" labelling. */
export const isLiveBackend = base.length > 0;

export const PREVIEW_LABEL = 'Interactive product preview';
