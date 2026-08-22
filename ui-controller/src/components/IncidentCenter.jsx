import { PlugZap, ShieldAlert } from 'lucide-react';
import IncidentList from './IncidentList.jsx';
import IncidentDetail from './IncidentDetail.jsx';

/**
 * Top-level Incident Center shell.
 *
 * Manages incident selection state. Renders IncidentList and IncidentDetail
 * side-by-side in the same grid style as LogsView.
 *
 * When the AI incident service is not deployed (aiAvailable === false),
 * shows an unobtrusive warning without breaking anything.
 */
export default function IncidentCenter({
  incidents, activeDetail, selectedId, onSelect, aiAvailable, error, cfg,
}) {
  return (
    <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[380px_1fr]">
      <section className="card pane flex flex-col p-3.5" aria-label="Incident list">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-[13.5px]">
            <ShieldAlert size={13} className="text-bad" aria-hidden="true" />
            Incidents
          </h2>
          <span className="font-mono text-[9.5px] text-faint">
            {incidents.length} incident{incidents.length !== 1 ? 's' : ''}
          </span>
        </div>

        {aiAvailable === false && (
          <div role="status" className="mb-2 flex items-start gap-2 rounded-xl
                                        border border-warn/45 bg-warn/10 px-3 py-2">
            <PlugZap size={13} className="mt-px shrink-0 text-warn" aria-hidden="true" />
            <p className="text-[10.5px] leading-relaxed text-dim">
              <b className="text-warn">AI incident service not deployed.</b>{' '}
              Teleop, scenarios, map and logs continue to work normally.
            </p>
          </div>
        )}

        {error && (
          <p className="mb-2 rounded-lg border border-bad/45 bg-bad/10 px-2 py-1
                        font-mono text-[10px] text-bad">{error}</p>
        )}

        <IncidentList incidents={incidents} selectedId={selectedId} onSelect={onSelect} />
      </section>

      <section className="card flex min-h-0 flex-col p-3.5" aria-label="Incident detail">
        <IncidentDetail incident={activeDetail} cfg={cfg} />
      </section>
    </div>
  );
}
