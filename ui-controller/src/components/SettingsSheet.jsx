import { useState } from 'react';
import { Save, X } from 'lucide-react';

const FIELDS = [
  ['api', 'OmniGuard API', 'http://HOST:8000', 'Every authorization decision is made here.'],
  ['bridge', 'Isaac bridge', 'http://HOST:8899', 'Motion only. Never consulted for policy.'],
  ['credential', 'Demo credential', 'fleet-agent-valid-token', 'Shared by both control planes.'],
  ['robot', 'Robot ID', 'robot-01', 'Must match the prim in the Isaac scene.'],
];

export default function SettingsSheet({ cfg, onSave, onClose }) {
  const [draft, setDraft] = useState(cfg);

  const save = () => {
    const cleaned = { ...draft };
    for (const k of ['api', 'bridge']) cleaned[k] = (cleaned[k] || '').trim().replace(/\/+$/, '');
    onSave(cleaned);
  };

  return (
    <section className="card a-rise mb-3 p-5" aria-label="Connection settings">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[15px]">Connection</h2>
        <button onClick={onClose} aria-label="Close settings"
          className="cursor-pointer rounded-lg p-1 text-faint transition-colors hover:text-txt">
          <X size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {FIELDS.map(([key, label, placeholder, hint]) => (
          <div key={key}>
            <label className="block">
              <span className="label mb-1.5">{label}</span>
              <input className="field" spellCheck="false" placeholder={placeholder}
                value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
            </label>
            <p className="mt-1.5 text-[10.5px] text-faint">{hint}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-[11.5px] text-faint">Stored in this browser only — no rebuild needed to change hosts.</p>
        <button onClick={save} className="btn btn-primary"><Save size={14} aria-hidden="true" />Save</button>
      </div>
    </section>
  );
}
