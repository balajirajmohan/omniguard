import { LogoMark, Wordmark } from './Logo';

const groups = [
  {
    title: 'Product',
    links: [
      { label: 'Platform', href: '#platform' },
      { label: 'How It Works', href: '#how-it-works' },
      { label: 'Use Cases', href: '#use-cases' },
      { label: 'Decision Lab', href: '#decision-lab' },
    ],
  },
  {
    title: 'Technical',
    links: [
      { label: 'Architecture', href: '#architecture' },
      { label: 'Digital Twin', href: '#digital-twin' },
      { label: 'Documentation', href: '#', placeholder: true },
      { label: 'GitLab / Repository', href: '#', placeholder: true },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-hairline bg-void">
      <div className="mx-auto w-full max-w-[1200px] px-5 py-14 sm:px-8">
        <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.4fr)_repeat(2,minmax(0,1fr))]">
          <div>
            <div className="flex items-center gap-2.5">
              <LogoMark size={24} />
              <Wordmark />
            </div>
            <p className="mt-3 font-mono text-[11px] tracking-[0.14em] text-cyan">
              ZERO TRUST FOR PHYSICAL AI
            </p>
            <p className="mt-5 max-w-sm text-[13px] leading-relaxed text-ink-faint">
              Policy-as-code for actions that move machines—not just data.
            </p>
          </div>

          {groups.map((g) => (
            <div key={g.title}>
              <h3 className="font-mono text-[10px] tracking-[0.16em] text-ink-faint">
                {g.title.toUpperCase()}
              </h3>
              <ul className="mt-4 space-y-2.5">
                {g.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="inline-flex items-center gap-1.5 text-[13.5px] text-ink-dim transition-colors duration-200 hover:text-cyan-bright"
                    >
                      {l.label}
                      {'placeholder' in l && l.placeholder && (
                        <span className="font-mono text-[9px] text-ink-faint">(soon)</span>
                      )}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-3 border-t border-hairline pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-mono text-[11px] text-warn/80">
            Hackathon prototype — not certified for production safety use.
          </p>
          <p className="font-mono text-[11px] text-ink-faint">
            © {new Date().getFullYear()} OmniGuard
          </p>
        </div>
      </div>
    </footer>
  );
}
