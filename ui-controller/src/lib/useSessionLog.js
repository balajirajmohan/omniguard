import { useCallback, useEffect, useRef, useState } from 'react';

/* Session history.
 *
 * "Reset demo" wipes backend state, which used to destroy the evidence of the
 * run that just happened. A session is archived on reset instead, so the
 * previous run stays readable and exportable afterwards.
 *
 * Held in localStorage, bounded, and best-effort: a private window or a full
 * quota must never break the console.
 */
const KEY = 'omniguard.sessions';
const MAX_SESSIONS = 25;
const MAX_ENTRIES = 400;

const now = () => new Date().toISOString();
const newId = () =>
  (globalThis.crypto?.randomUUID?.() ?? `s-${Date.now()}-${Math.random().toString(16).slice(2)}`);

function readStore() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(raw) ? raw : [];
  } catch { return []; }
}

function writeStore(sessions) {
  try {
    localStorage.setItem(KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
  } catch { /* quota or private mode — history is a convenience, not a guarantee */ }
}

/** Stable identity for a decision, so polling the same event never duplicates it. */
const keyOf = (e) =>
  `${e.timestamp ?? ''}|${e.final_decision ?? ''}|${e.device_id ?? ''}|${e.destination ?? ''}|${e.speed ?? ''}`;

export function useSessionLog() {
  const [sessions, setSessions] = useState(readStore);
  const [current, setCurrent] = useState([]);
  const seen = useRef(new Set());
  const startedAt = useRef(now());

  /* Absorb backend events as they are polled. Newest-first in, oldest-first out. */
  const record = useCallback((events) => {
    if (!Array.isArray(events) || !events.length) return;
    const fresh = [];
    for (const e of [...events].reverse()) {
      const k = keyOf(e);
      if (!k.trim() || seen.current.has(k)) continue;
      seen.current.add(k);
      fresh.push({ ...e, source: 'backend', recorded_at: now() });
    }
    if (fresh.length) setCurrent((prev) => [...prev, ...fresh].slice(-MAX_ENTRIES));
  }, []);

  /** Client-side moments the backend has no event for (lease issued, e-stop). */
  const note = useCallback((entry) => {
    setCurrent((prev) => [...prev, {
      ...entry, source: entry.source ?? 'ui', recorded_at: now(),
    }].slice(-MAX_ENTRIES));
  }, []);

  /** Close the current run and keep it. Called before the backend is reset. */
  const archive = useCallback((meta = {}) => {
    let archived = null;
    setCurrent((entries) => {
      if (entries.length) {
        archived = {
          id: newId(),
          started_at: startedAt.current,
          ended_at: now(),
          entry_count: entries.length,
          ...meta,
          entries,
        };
      }
      return [];
    });
    seen.current = new Set();
    startedAt.current = now();
    /* setSessions runs after the state updater above has produced `archived`. */
    queueMicrotask(() => {
      if (!archived) return;
      setSessions((prev) => {
        const next = [archived, ...prev].slice(0, MAX_SESSIONS);
        writeStore(next);
        return next;
      });
    });
  }, []);

  const removeSession = useCallback((id) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      writeStore(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setSessions([]);
    writeStore([]);
  }, []);

  /* Keep the live run recoverable if the tab is closed mid-demo. */
  useEffect(() => {
    const persist = () => {
      if (!current.length) return;
      const live = {
        id: 'live-' + startedAt.current,
        started_at: startedAt.current,
        ended_at: now(),
        entry_count: current.length,
        label: 'unfinished session',
        entries: current,
      };
      writeStore([live, ...readStore().filter((s) => !String(s.id).startsWith('live-'))]);
    };
    window.addEventListener('pagehide', persist);
    return () => window.removeEventListener('pagehide', persist);
  }, [current]);

  return { sessions, current, record, note, archive, removeSession, clearAll };
}

/* ----------------------------------------------------------------- export */

function download(filename, mime, text) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  /* Revoking immediately can cancel the download in some browsers. */
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

const stamp = (iso) => (iso ?? now()).replace(/[:.]/g, '-').slice(0, 19);

export function exportJson(name, payload) {
  download(`omniguard-${name}.json`, 'application/json', JSON.stringify(payload, null, 2));
}

const CSV_COLUMNS = [
  ['timestamp', (e) => e.timestamp ?? e.recorded_at],
  ['final_decision', (e) => e.final_decision],
  ['policy_decision', (e) => e.policy_decision],
  ['caught_by', (e) => e.caught_by],
  ['hard_policy_would_block', (e) => e.hard_policy_would_block],
  ['anomaly_risk_score', (e) => e.anomaly_risk_score],
  ['agent_id', (e) => e.agent_id],
  ['device_id', (e) => e.device_id],
  ['destination', (e) => e.destination],
  ['speed', (e) => e.speed],
  ['reasons', (e) => (e.reasons ?? []).join(' ')],
  ['actions', (e) => (e.actions ?? []).join(' ')],
  /* AI provenance fields — appended, never removing existing columns. */
  ['decision_source', (e) => e.decision_source],
  ['anomaly_model_version', (e) => e.anomaly_model_version],
  ['ai_mode', (e) => e.ai_mode],
  ['incident_id', (e) => e.incident_id],
  ['response_playbook', (e) => e.response_playbook],
  ['containment_ack', (e) => e.containment_ack],
];

/* Quote everything and double embedded quotes — reason strings are free text. */
const cell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;

export function toCsv(entries) {
  const rows = [CSV_COLUMNS.map(([h]) => cell(h)).join(',')];
  for (const e of entries) rows.push(CSV_COLUMNS.map(([, get]) => cell(get(e))).join(','));
  return rows.join('\n');
}

export function exportCsv(name, entries) {
  download(`omniguard-${name}.csv`, 'text/csv;charset=utf-8', toCsv(entries));
}

export const exportSession = (s) => exportJson(`session-${stamp(s.started_at)}`, s);
export const exportSessionCsv = (s) => exportCsv(`decisions-${stamp(s.started_at)}`, s.entries ?? []);
export const exportAllSessions = (sessions) =>
  exportJson(`sessions-${stamp()}`, { exported_at: now(), session_count: sessions.length, sessions });
