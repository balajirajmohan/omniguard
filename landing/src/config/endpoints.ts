/**
 * Single source of truth for backend wiring.
 *
 * The UI ships with local mock data (see `src/data/demoData.ts`). When
 * `VITE_OMNIGUARD_API_BASE` is set, the same components can fetch live
 * decisions without any redesign — only the data source changes.
 */

const base = (import.meta.env.VITE_OMNIGUARD_API_BASE ?? '').replace(/\/$/, '');

export const endpoints = {
  base,
  /** Broker / model / simulator readiness. */
  health: `${base}/health`,
  /** Submit a command for authorization; returns a decision trace. */
  command: `${base}/command`,
  /** Historical containment events. */
  incidents: `${base}/incidents`,
} as const;

/** Route to the full operations console. */
export const DEMO_ROUTE = import.meta.env.VITE_OMNIGUARD_DEMO_ROUTE ?? '/demo';

/** False until a backend is configured — drives the "product preview" labelling. */
export const isLiveBackend = base.length > 0;

export const PREVIEW_LABEL = isLiveBackend
  ? 'Live decision stream'
  : 'Interactive product preview';
