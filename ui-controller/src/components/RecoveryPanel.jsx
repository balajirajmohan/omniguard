import { useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock, Info, Loader2, Play, RefreshCw, ShieldAlert, ShieldCheck, XCircle } from 'lucide-react';
import { advanceIncidentRecovery, normalizeRecoveryState } from '../lib/omniguard.js';

const EVIDENCE_BY_STATE = {
  CREDENTIAL_ROTATION_REQUIRED: {
    old_credential_revoked: true,
    new_credential_issued: true,
  },
  DEVICE_ATTESTATION_REQUIRED: {
    device_attested: true,
  },
  OPERATOR_REAUTHENTICATION_REQUIRED: {
    operator_reauthenticated: true,
  },
  LIMITED_ACCESS: {
    related_incidents_closed: true,
  },
  ENHANCED_MONITORING: {
    risk_below_recovery_threshold: true,
  },
};

export default function RecoveryPanel({ incidentId, raw, cfg, onRefresh }) {
  const recovery = normalizeRecoveryState(raw);
  const [confirmingAction, setConfirmingAction] = useState(null); // 'start' | 'advance' | null
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!recovery) {
    return (
      <div className="space-y-2">
        <p className="text-[11px] text-faint">
          No active recovery workflow for this incident.
        </p>
        <button
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await advanceIncidentRecovery(cfg, incidentId, {});
              onRefresh?.();
            } catch (err) {
              setError(err.message);
            } finally {
              setBusy(false);
            }
          }}
          disabled={busy}
          className="btn btn-sm"
        >
          {busy ? <Loader2 size={11} className="animate-spin" aria-hidden="true" /> : <Play size={11} aria-hidden="true" />}
          Initialize recovery
        </button>
        {error && <p className="rounded-lg border border-bad/45 bg-bad/10 px-2 py-1 font-mono text-[10px] text-bad">{error}</p>}
      </div>
    );
  }

  const isRestored =
    recovery.state === 'RESTORED' ||
    recovery.state === 'FULL_ACCESS_RESTORED' ||
    recovery.state === 'FULL_RESTORED' ||
    recovery.runtime_access_restored;

  const handleAdvance = async () => {
    setBusy(true);
    setError(null);
    try {
      const evidence = EVIDENCE_BY_STATE[recovery.state] || { device_attested: true };
      await advanceIncidentRecovery(cfg, incidentId, { evidence });
      onRefresh?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setConfirmingAction(null);
    }
  };

  const evidenceEntries = Object.entries(recovery.evidence ?? {});

  return (
    <div className="space-y-3">
      {/* Overview Card */}
      <div className="rounded-xl border border-line bg-sunken/70 p-3 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {recovery.runtime_access_restored ? (
              <ShieldCheck size={14} className="text-ok shrink-0" aria-hidden="true" />
            ) : (
              <ShieldAlert size={14} className="text-warn shrink-0" aria-hidden="true" />
            )}
            <span className="font-mono text-[11px] font-bold text-txt">
              State: {recovery.state ?? 'INITIAL'}
            </span>
          </div>
          {recovery.simulated && (
            <span className="chip border-warn/45 bg-warn/10 text-warn text-[9.5px]">
              SIMULATED FOR DEMO
            </span>
          )}
        </div>

        {recovery.label && (
          <p className="text-[11px] leading-relaxed text-dim">{recovery.label}</p>
        )}

        <div className="grid grid-cols-2 gap-2 font-mono text-[10px] pt-1">
          <div className="flex items-center justify-between rounded-md border border-line bg-elevated/50 px-2 py-1">
            <span className="text-faint">IdP Workflow:</span>
            <span className={recovery.idp_workflow_complete ? 'text-ok font-semibold' : 'text-faint'}>
              {recovery.idp_workflow_complete ? 'COMPLETE' : 'PENDING'}
            </span>
          </div>
          <div className="flex items-center justify-between rounded-md border border-line bg-elevated/50 px-2 py-1">
            <span className="text-faint">Runtime Access:</span>
            <span className={recovery.runtime_access_restored ? 'text-ok font-semibold' : 'text-bad font-semibold'}>
              {recovery.runtime_access_restored ? 'RESTORED' : 'RESTRICTED'}
            </span>
          </div>
        </div>
      </div>

      {/* Mandatory Notice: Completed simulated IdP recovery does not restore runtime access */}
      {recovery.idp_workflow_complete && !recovery.runtime_access_restored && (
        <div className="flex items-start gap-2.5 rounded-xl border border-warn/45 bg-warn/10 px-3 py-2.5" role="status">
          <Info size={14} className="mt-0.5 shrink-0 text-warn" aria-hidden="true" />
          <p className="text-[11px] leading-relaxed text-warn">
            <b>IdP workflow complete does not mean runtime access has been restored.</b>{' '}
            Completed simulated IdP recovery does not restore runtime robot access until verified by backend security.
          </p>
        </div>
      )}

      {/* Evidence Checklist */}
      {evidenceEntries.length > 0 && (
        <div>
          <span className="label mb-1">Recovery Evidence</span>
          <ul className="space-y-1 font-mono text-[10px]">
            {evidenceEntries.map(([key, val]) => {
              const isTrue = val === true || val === 'verified' || val === 'COMPLETE';
              return (
                <li key={key} className="flex items-center justify-between rounded-md border border-line bg-sunken/50 px-2.5 py-1">
                  <span className="text-faint">{key.replace(/_/g, ' ')}</span>
                  <span className={`flex items-center gap-1 text-[9px] font-bold ${isTrue ? 'text-ok' : 'text-faint'}`}>
                    {isTrue ? <CheckCircle2 size={10} aria-hidden="true" /> : <Clock size={10} aria-hidden="true" />}
                    {String(val).toUpperCase()}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* History timeline */}
      {recovery.history.length > 0 && (
        <div>
          <span className="label mb-1">Transition History</span>
          <ol className="space-y-0.5 font-mono text-[9.5px]">
            {recovery.history.map((h, i) => (
              <li key={i} className="flex items-center justify-between rounded border border-line/40 px-2 py-0.5 text-faint">
                <span>{typeof h === 'string' ? h : h.state ?? h.action ?? JSON.stringify(h)}</span>
                {h.timestamp && <span className="tabular-nums">{new Date(h.timestamp).toLocaleTimeString()}</span>}
              </li>
            ))}
          </ol>
        </div>
      )}

      {error && (
        <p className="rounded-lg border border-bad/45 bg-bad/10 px-2 py-1 font-mono text-[10px] text-bad">{error}</p>
      )}

      {/* Advance / Initialize Actions */}
      {!isRestored && (!confirmingAction ? (
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => setConfirmingAction('advance')}
            disabled={busy}
            className="btn btn-sm"
            aria-label="Advance recovery"
          >
            <RefreshCw size={11} aria-hidden="true" />
            Advance recovery stage
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-xl border border-warn/45 bg-warn/10 px-3 py-2">
          <AlertTriangle size={13} className="shrink-0 text-warn" aria-hidden="true" />
          <p className="flex-1 text-[11px] text-warn">
            Submit recovery evidence to advance stage?
          </p>
          <div className="flex gap-1.5">
            <button onClick={() => setConfirmingAction(null)} disabled={busy} className="btn btn-sm text-faint">
              Cancel
            </button>
            <button onClick={handleAdvance} disabled={busy} className="btn btn-sm btn-primary">
              {busy ? <Loader2 size={11} className="animate-spin" aria-hidden="true" /> : <CheckCircle2 size={11} aria-hidden="true" />}
              {busy ? 'Advancing…' : 'Confirm'}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
