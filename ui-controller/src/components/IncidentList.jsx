import { ShieldAlert } from 'lucide-react';
import { riskBand } from '../lib/omniguard.js';

const TONE = {
  normal: '', warning: 'text-warn', critical: 'text-bad',
};

const STATUS_CLS = {
  OPEN: 'border-bad/45 bg-bad/10 text-bad',
  ACTIVE: 'border-warn/45 bg-warn/10 text-warn',
  CONTAINED: 'border-info/45 bg-info/10 text-info',
  INVESTIGATING: 'border-violet/45 bg-violet/10 text-violet',
  RESOLVED: 'border-ok/45 bg-ok/10 text-ok',
  CLOSED: 'border-faint/45 bg-faint/10 text-faint',
};

const when = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString([], { hour12: false }); } catch { return iso; }
};

/**
 * Incident list table.
 *
 * Columns: Incident ID, Status, First seen, Last seen, Event count,
 * Agent/device/robot, Decision source, Risk, Playbook, Containment status.
 */
export default function IncidentList({ incidents, selectedId, onSelect }) {
  if (!incidents.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8">
        <ShieldAlert size={20} className="text-faint" aria-hidden="true" />
        <p className="text-[11.5px] text-faint">No incidents recorded.</p>
      </div>
    );
  }

  return (
    <div className="pane">
      <table className="w-full border-collapse" aria-label="Incident list">
        <thead className="sticky top-0 bg-surface/95 backdrop-blur">
          <tr className="border-b border-line">
            {['ID', 'Status', 'First seen', 'Last seen', 'Events', 'Device',
              'Source', 'Risk', 'Playbook', 'Containment'].map((h) => (
              /* Not .label — it sets display:block, which drops a <th> out of the
                 table layout and misaligns the headers. */
              <th key={h}
                className="py-1.5 pr-2 text-left text-[9px] font-semibold uppercase
                           tracking-[.16em] whitespace-nowrap text-faint">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => {
            const on = inc.incident_id === selectedId;
            const risk = inc.anomaly_risk_score;
            const band = risk != null ? riskBand(risk) : 'normal';
            return (
              <tr key={inc.incident_id ?? inc.raw?.id}
                onClick={() => onSelect?.(inc.incident_id)}
                className={`cursor-pointer border-b border-line/60 transition-colors
                            ${on ? 'bg-info/10' : 'hover:bg-elevated/60'}`}
                role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') onSelect?.(inc.incident_id); }}
                aria-selected={on}>
                <td className="py-1.5 pr-2 font-mono text-[10px] text-info whitespace-nowrap">
                  {inc.incident_id ?? '—'}
                </td>
                <td className="py-1.5 pr-2">
                  <span className={`inline-block rounded-full border px-1.5 py-px
                                    font-mono text-[8.5px] font-bold tracking-wide
                                    ${STATUS_CLS[inc.status] ?? ''}`}>
                    {inc.status ?? '—'}
                  </span>
                </td>
                <td className="py-1.5 pr-2 font-mono text-[9.5px] text-faint whitespace-nowrap"
                  title={inc.first_seen ?? undefined}>
                  {when(inc.first_seen)}
                </td>
                <td className="py-1.5 pr-2 font-mono text-[9.5px] text-faint whitespace-nowrap"
                  title={inc.last_seen ?? undefined}>
                  {when(inc.last_seen)}
                </td>
                <td className="py-1.5 pr-2 font-mono text-[10px] tabular-nums text-dim">
                  {inc.event_count ?? '—'}
                </td>
                <td className="py-1.5 pr-2 font-mono text-[9.5px] text-dim whitespace-nowrap">
                  {inc.device_id ?? inc.agent_id ?? '—'}
                </td>
                <td className="py-1.5 pr-2 font-mono text-[9.5px] text-dim whitespace-nowrap">
                  {inc.decision_source?.replace(/_/g, ' ') ?? '—'}
                </td>
                <td className={`py-1.5 pr-2 font-mono text-[10px] tabular-nums
                               ${TONE[band]}`}>
                  {risk != null ? risk.toFixed(2) : '—'}
                </td>
                <td className="py-1.5 pr-2 font-mono text-[9.5px] text-dim whitespace-nowrap">
                  {inc.response_playbook?.replace(/_/g, ' ') ?? '—'}
                </td>
                <td className="py-1.5 font-mono text-[9.5px] text-dim whitespace-nowrap">
                  {inc.containment_status ?? '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
