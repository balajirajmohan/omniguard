import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { LogoMark, Wordmark } from './Logo';
import { ButtonLink } from './ui/Button';
import { useScrolled } from '../hooks/useMotionPrefs';
import { DEMO_ROUTE } from '../config/endpoints';

const links = [
  { label: 'Platform', href: '#platform' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Digital Twin', href: '#digital-twin' },
  { label: 'Use Cases', href: '#use-cases' },
  { label: 'Architecture', href: '#architecture' },
];

export function Nav() {
  const scrolled = useScrolled(12);
  const [open, setOpen] = useState(false);

  // Prevent background scroll while the mobile sheet is open.
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,backdrop-filter] duration-300 ${
        scrolled
          ? 'border-b border-hairline bg-graphite/85 backdrop-blur-xl'
          : 'border-b border-transparent bg-transparent'
      }`}
    >
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 w-full max-w-[1200px] items-center gap-6 px-5 sm:px-8"
      >
        <Link
          to="/"
          className="flex items-center gap-2.5 rounded-md"
          aria-label="OmniGuard home"
        >
          <LogoMark size={26} />
          <Wordmark />
        </Link>

        <ul className="ml-2 hidden items-center gap-1 lg:flex">
          {links.map((l) => (
            <li key={l.href}>
              <a
                href={l.href}
                className="relative rounded-md px-3 py-2 text-[13.5px] text-ink-dim transition-colors duration-200 hover:text-ink"
              >
                {l.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="ml-auto flex items-center gap-2">
          <a
            href="#architecture"
            className="hidden rounded-md px-3 py-2 text-[13.5px] text-ink-dim transition-colors duration-200 hover:text-cyan-bright sm:inline-block"
          >
            View Architecture
          </a>
          <ButtonLink href={DEMO_ROUTE} size="sm" className="hidden sm:inline-flex">
            Launch Live Demo
          </ButtonLink>

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'}
            className="grid h-10 w-10 cursor-pointer place-items-center rounded-md border border-hairline-strong text-ink-dim transition-colors hover:text-ink lg:hidden"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
              {open ? (
                <path
                  d="M4 4l10 10M14 4L4 14"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              ) : (
                <path
                  d="M2.5 5h13M2.5 9h13M2.5 13h13"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              )}
            </svg>
          </button>
        </div>
      </nav>

      {open && (
        <div
          id="mobile-nav"
          className="border-t border-hairline bg-graphite/97 backdrop-blur-xl lg:hidden"
        >
          <ul className="mx-auto flex max-w-[1200px] flex-col gap-1 px-5 py-4 sm:px-8">
            {links.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="block rounded-md px-3 py-3 text-[15px] text-ink-dim transition-colors hover:bg-surface-2 hover:text-ink"
                >
                  {l.label}
                </a>
              </li>
            ))}
            <li className="mt-2 sm:hidden">
              <ButtonLink href={DEMO_ROUTE} className="w-full">
                Launch Live Demo
              </ButtonLink>
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}
