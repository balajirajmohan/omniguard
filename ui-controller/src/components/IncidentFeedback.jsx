import { useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, MessageSquare, User } from 'lucide-react';
import { submitIncidentFeedback } from '../lib/omniguard.js';

const CLASSIFICATIONS = [
  { value: 'CONFIRMED_ATTACK',      label: 'Confirmed attack' },
  { value: 'FALSE_POSITIVE',        label: 'False positive' },
  { value: 'OPERATOR_ERROR',        label: 'Operator error' },
  { value: 'MISCONFIGURATION',      label: 'Misconfiguration' },
  { value: 'EXPECTED_MAINTENANCE',   label: 'Expected maintenance' },
  { value: 'POLICY_GAP',            label: 'Policy gap' },
  { value: 'UNKNOWN',               label: 'Unknown' },
];

const clock = (iso) => {
  if (!iso) return null;
  try { return new Date(iso).toLocaleString([], { hour12: false }); } catch { return null; }
};

/**
 * Incident feedback controls.
 *
 * Requirements:
 * - Explicit operator selection (radio buttons, not auto-label)
 * - Optional comment
 * - Confirmation before submission
 * - Explains: "Feedback becomes reviewed training evidence.
 *   It does not immediately retrain or deploy a model."
 * - Does NOT automatically label based on LLM summary
 */
export default function IncidentFeedback({ incidentId, existingFeedback, cfg }) {
  const [classification, setClassification] = useState(null);
  const [comment, setComment] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await submitIncidentFeedback(cfg, incidentId, {
        classification,
        comment: comment.trim() || undefined,
      });
      setSubmitted(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  /* Show saved feedback if returned by the backend */
  if (existingFeedback || submitted) {
    const fb = existingFeedback ?? { classification, comment: comment.trim() || undefined };
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 rounded-xl border border-ok/45 bg-ok/10 px-3 py-2">
          <CheckCircle2 size={13} className="shrink-0 text-ok" aria-hidden="true" />
          <span className="text-[11px] font-semibold text-ok">Feedback submitted</span>
        </div>
        <dl className="space-y-1 font-mono text-[10px]">
          <div className="flex gap-2">
            <dt className="text-faint">Classification:</dt>
            <dd className="text-dim">{fb.classification?.replace(/_/g, ' ')}</dd>
          </div>
          {fb.comment && (
            <div className="flex gap-2">
              <dt className="text-faint">Comment:</dt>
              <dd className="text-dim">{fb.comment}</dd>
            </div>
          )}
          {fb.reviewed_by && (
            <div className="flex items-center gap-2">
              <User size={9} className="text-faint" aria-hidden="true" />
              <dt className="text-faint">Reviewed by:</dt>
              <dd className="text-dim">{fb.reviewed_by}</dd>
            </div>
          )}
          {fb.reviewed_at && (
            <div className="flex gap-2">
              <dt className="text-faint">Reviewed at:</dt>
              <dd className="text-dim">{clock(fb.reviewed_at)}</dd>
            </div>
          )}
        </dl>
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <p className="text-[10.5px] leading-relaxed text-faint">
        Feedback becomes reviewed training evidence. It does not immediately retrain or deploy a model.
      </p>

      {/* Classification selection */}
      <fieldset>
        <legend className="label mb-1.5">Classification</legend>
        <div className="grid gap-1">
          {CLASSIFICATIONS.map(({ value, label }) => (
            <label key={value}
              className={`flex cursor-pointer items-center gap-2.5 rounded-lg border
                          px-2.5 py-1.5 text-[10.5px] transition-colors
                          ${classification === value
                            ? 'border-info/55 bg-info/10 text-info'
                            : 'border-line bg-sunken/70 text-dim hover:border-line-hi'}`}>
              <input type="radio" name="feedback-classification" value={value}
                checked={classification === value}
                onChange={() => setClassification(value)}
                className="sr-only" />
              <span className={`flex size-3 items-center justify-center rounded-full border
                               ${classification === value
                                 ? 'border-info bg-info'
                                 : 'border-faint/60'}`}>
                {classification === value && (
                  <span className="size-1.5 rounded-full bg-surface" />
                )}
              </span>
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      {/* Optional comment */}
      <div>
        <label className="label mb-1.5" htmlFor="feedback-comment">
          <MessageSquare size={9} className="inline mr-1" aria-hidden="true" />
          Comment (optional)
        </label>
        <textarea id="feedback-comment" value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={2} className="field resize-none text-[11px]"
          placeholder="Additional context…" />
      </div>

      {error && (
        <p className="rounded-lg border border-bad/45 bg-bad/10 px-2 py-1 font-mono
                      text-[10px] text-bad">{error}</p>
      )}

      {/* Submit with confirmation */}
      {!confirming ? (
        <button onClick={() => setConfirming(true)}
          disabled={!classification}
          className="btn btn-sm"
          aria-label="Submit incident feedback">
          Submit feedback
        </button>
      ) : (
        <div className="flex items-center gap-2 rounded-xl border border-warn/45 bg-warn/10
                        px-3 py-2">
          <AlertTriangle size={13} className="shrink-0 text-warn" aria-hidden="true" />
          <p className="flex-1 text-[11px] text-warn">
            Submit "{classification?.replace(/_/g, ' ')}" classification?
          </p>
          <div className="flex gap-1.5">
            <button onClick={() => setConfirming(false)} disabled={busy}
              className="btn btn-sm text-faint">Cancel</button>
            <button onClick={submit} disabled={busy} className="btn btn-sm btn-primary">
              {busy ? <Loader2 size={11} className="animate-spin" aria-hidden="true" />
                    : <CheckCircle2 size={11} aria-hidden="true" />}
              {busy ? 'Submitting…' : 'Confirm'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
