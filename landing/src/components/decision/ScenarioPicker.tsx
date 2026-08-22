import { scenarios, type ScenarioId } from '../../data/demoData';

const tone: Record<ScenarioId, { dot: string; active: string }> = {
  normal: { dot: 'bg-allow', active: 'border-allow/50 bg-allow/8' },
  stolen: { dot: 'bg-deny', active: 'border-deny/55 bg-deny/10' },
  anomaly: { dot: 'bg-warn', active: 'border-warn/50 bg-warn/8' },
  manipulation: { dot: 'bg-deny', active: 'border-deny/55 bg-deny/10' },
};

/** Radio-style scenario selector. Arrow keys work via native radio semantics. */
export function ScenarioPicker({
  selected,
  onSelect,
  size = 'md',
}: {
  selected: ScenarioId;
  onSelect: (id: ScenarioId) => void;
  size?: 'md' | 'lg';
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Decision scenario"
      className={size === 'lg' ? 'grid grid-cols-1 gap-2.5 sm:grid-cols-2' : 'space-y-2.5'}
    >
      {scenarios.map((s) => {
        const active = s.id === selected;
        return (
          <button
            key={s.id}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onSelect(s.id)}
            className={`group w-full cursor-pointer rounded-lg border p-3.5 text-left transition-all duration-200 ${
              active
                ? `${tone[s.id].active} shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]`
                : 'border-hairline bg-surface-2/40 hover:border-hairline-strong hover:bg-surface-2/80'
            }`}
          >
            <span className="flex items-center gap-2.5">
              <span
                className={`h-2 w-2 shrink-0 rounded-full transition-opacity duration-200 ${tone[s.id].dot} ${
                  active ? 'opacity-100' : 'opacity-40 group-hover:opacity-70'
                }`}
              />
              <span
                className={`text-[13.5px] font-medium ${active ? 'text-ink' : 'text-ink-dim group-hover:text-ink'}`}
              >
                {s.name}
              </span>
            </span>
            <span className="mt-1.5 block pl-[18px] text-[12px] leading-relaxed text-ink-faint">
              {s.blurb}
            </span>
          </button>
        );
      })}
    </div>
  );
}
