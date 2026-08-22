import { useState } from 'react';
import { AlertTriangle, CheckCircle2, Clock, Loader2, RefreshCw, XCircle } from 'lucide-react';
import { advanceIncidentRecovery, normalizeRecoveryState } from '../lib/omniguard.js';

/* Explicit status values from the backend. */
const STATUS_LOOK = {
  pending:      { Icon: Clock,        cls: 'text-faint',  word: 'PENDING' },
  verified:     { Icon: CheckCircle2, cls: 'text-ok',     word: 'VERIFIED' },
  failed:       { Icon: XCircle,      cls: 'text-bad',    word: 'FAILED' },
  simulated:    { Icon: AlertTriangle, cls: 'text-warn',  word: 'SIMULATED FOR DEMO' },
  not_required: { Icon: CheckCircle2, cls: 'text-faint',  word: 'NOT REQUIRED' },
};

const STEP_LABELS = [
  ['old_credential_revoked',    'Old credential revoked'],
  ['new_credential_issued',     'New credential issued'],
  ['device_attested',           'Device attested'],
  ['operator_reauthenticated',  'Operator reauthenticated'],
  ['related_incidents_closed',  'Related incidents closed'],
  ['risk_below_threshold',      'Risk below recovery threshold'],
  ['limited_access_enabled',    'Limited access enabled'],
  ['enhanced_monitoring_active','Enhanced monitoring active'],
  ['full_access_restored',      'Full access restored'],
];

/**
 * Recovery progress panel.
 *
 * Requirements:
 * - Uses explicit status values (pending/verified/failed/simulated/not_required)
 * - Simulated operations show "SIMULATED FOR DEMO"
 * - Recovery requires an explicit authorized operator action
 * - Does NOT automatically call the recovery endpoint
 * - Does NOT skip backend-required recovery stages
 */
export default function RecoveryPanel({ incidentId, raw, cfg }) {
  const recovery = normalizeRecoveryState(raw);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!recovery) {
    return (
      <p className="text-[11px] text-faint">
        No recovery state available from the backend.
      </p>
    );
  }

  const advance = async () => {
    setBusy(true);
    setError(null);
    try {
      await advanceIncidentRecovery(cfg, incidentId, { action: 'advance' });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  return (
    <div className="space-y-2.5">
      {/* Recovery checklist */}
      <ol className="space-y-1" aria-label="Recovery progress">
        {STEP_LABELS.map(([key, label]) => {
          const value = recovery[key];
          if (value == null) return null;
          const look = STATUS_LOOK[value] ?? STATUS_LOOK.pending;
          const { Icon } = look;
          return (
            <li key={key} className="flex items-center gap-2.5 rounded-lg border border-line
                                     bg-sunken/70 px-2.5 py-1.5">
              <Icon size={12} className={`shrink-0 ${look.cls}`} aria-hidden="true" />
              <span className="flex-1 text-[10.5px] text-dim">{label}</span>
              <span className={`font-mono text-[9px] font-bold tracking-wide ${look.cls}`}
                role="status" aria-label={`${label}: ${look.word}`}>
                {look.word}
              </span>
            </li>
          );
        })}
      </ol>

      {/* Current stage */}
      {recovery.current_stage && (
        <p className="font-mono text-[10px] text-faint">
          Current stage: {recovery.current_stage.replace(/_/g, ' ')}
        </p>
      )}

      {error && (
        <p className="rounded-lg border border-bad/45 bg-bad/10 px-2 py-1 font-mono
                      text-[10px] text-bad">{error}</p>
      )}

      {/* Advance recovery — requires explicit confirmation */}
      {recovery.can_advance && !confirming && (
        <button onClick={() => setConfirming(true)} className="btn btn-sm"
          aria-label="Advance recovery to next stage">
          <RefreshCw size={11} aria-hidden="true" />
          Advance recovery
        </button>
      )}

      {confirming && (
        <div className="flex items-center gap-2 rounded-xl border border-warn/45 bg-warn/10
                        px-3 py-2">
          <AlertTriangle size={13} className="shrink-0 text-warn" aria-hidden="true" />
          <p className="flex-1 text-[11px] text-warn">
            This will advance the recovery process. Continue?
          </p>
          <div className="flex gap-1.5">
            <button onClick={() => setConfirming(false)} disabled={busy}
              className="btn btn-sm text-faint">Cancel</button>
            <button onClick={advance} disabled={busy} className="btn btn-sm btn-primary">
              {busy ? <Loader2 size={11} className="animate-spin" aria-hidden="true" />
                    : <CheckCircle2 size={11} aria-hidden="true" />}
              {busy ? 'Advancing…' : 'Confirm'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
