import type { Field } from '../../data/demoData';
import { statusTone, toneText } from '../ui/Primitives';

/** Key/value command context, rendered in mono so IDs stay scannable. */
export function FieldTable({ fields }: { fields: Field[] }) {
  return (
    <dl className="divide-y divide-hairline/70 overflow-hidden rounded-lg border border-hairline">
      {fields.map((f) => (
        <div key={f.key} className="flex items-baseline gap-3 px-3.5 py-2.5">
          <dt className="shrink-0 font-mono text-[11px] text-ink-faint">{f.key}</dt>
          <dd
            className={`ml-auto break-all text-right font-mono text-[11.5px] font-medium ${toneText[statusTone(f.status)]}`}
          >
            {f.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
