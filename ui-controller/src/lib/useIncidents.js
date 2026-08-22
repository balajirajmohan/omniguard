import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getAiStatus, getIncident, listIncidents, normalizeAiStatus,
  normalizeIncidentDetail, normalizeIncidentSummary,
} from './omniguard.js';

/* Polling tiers, all independent of the teleop loop.
 *
 * Incident list:   ~4 s  when the Incident Center is visible
 * Active detail:   ~1.5 s while investigation is pending, then stop
 * Closed detail:   fetch on demand, never polled
 *
 * Every poll checks document.hidden and pauses if the tab is backgrounded.
 * AbortControllers cancel in-flight reads when the component unmounts. */

const LIST_POLL_MS = 4000;
const DETAIL_POLL_MS = 1500;
const DETAIL_SETTLED_MS = 10_000;

export function useIncidents(cfg, { enabled = false } = {}) {
  const cfgRef = useRef(cfg);
  cfgRef.current = cfg;

  const [aiStatus, setAiStatus] = useState(null);
  const [aiAvailable, setAiAvailable] = useState(null); // null = unknown
  const [incidents, setIncidents] = useState([]);
  const [activeIncident, setActiveIncident] = useState(null);
  const [activeDetail, setActiveDetail] = useState(null);
  const [error, setError] = useState(null);
  const acRef = useRef(null);

  /* ------------------------------------------------------------- AI status */
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    const check = async () => {
      try {
        const raw = await getAiStatus(cfgRef.current);
        if (alive) {
          const s = normalizeAiStatus(raw);
          setAiStatus(s);
          setAiAvailable(s.available);
        }
      } catch {
        if (alive) {
          setAiStatus(normalizeAiStatus(null));
          setAiAvailable(false);
        }
      }
    };
    check();
    return () => { alive = false; };
  }, [enabled, cfg.api]);

  /* --------------------------------------------------------- incident list */
  useEffect(() => {
    if (!enabled) return undefined;
    let alive = true;
    let handle;

    const poll = async () => {
      if (document.hidden) { handle = setTimeout(poll, LIST_POLL_MS); return; }
      try {
        const raw = await listIncidents(cfgRef.current);
        if (alive) {
          const list = (Array.isArray(raw) ? raw : raw?.incidents ?? [])
            .map(normalizeIncidentSummary)
            .filter(Boolean);
          setIncidents(list);
          setAiAvailable(true);
          setError(null);
        }
      } catch (err) {
        if (alive) {
          if (err.status === 404) {
            setAiAvailable(false);
            setIncidents([]);
          } else {
            setError(err.message);
          }
        }
      }
      if (alive) handle = setTimeout(poll, LIST_POLL_MS);
    };

    poll();
    const onVis = () => { if (!document.hidden && alive) { clearTimeout(handle); poll(); } };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      alive = false;
      clearTimeout(handle);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [enabled, cfg.api]);

  /* ------------------------------------------------------- active incident */
  const selectIncident = useCallback((id) => {
    setActiveIncident(id);
    setActiveDetail(null);
  }, []);

  useEffect(() => {
    if (!enabled || !activeIncident) return undefined;
    let alive = true;
    let handle;

    const poll = async () => {
      if (document.hidden) { handle = setTimeout(poll, DETAIL_POLL_MS); return; }
      try {
        const raw = await getIncident(cfgRef.current, activeIncident);
        if (alive) {
          const detail = normalizeIncidentDetail(raw);
          setActiveDetail(detail);
          setError(null);
          /* Settled incidents poll much less frequently. */
          const settled = detail?.status === 'CLOSED' || detail?.status === 'RESOLVED';
          if (alive) handle = setTimeout(poll, settled ? DETAIL_SETTLED_MS : DETAIL_POLL_MS);
        }
      } catch (err) {
        if (alive) setError(err.message);
        if (alive) handle = setTimeout(poll, DETAIL_POLL_MS);
      }
    };

    poll();
    return () => {
      alive = false;
      clearTimeout(handle);
    };
  }, [enabled, activeIncident, cfg.api]);

  return {
    aiStatus, aiAvailable, incidents, activeIncident, activeDetail, error,
    selectIncident,
  };
}
