import type { ReactNode } from 'react';

export type Tone = 'neutral' | 'cyan' | 'allow' | 'warn' | 'deny';

export const toneText: Record<Tone, string> = {
  neutral: 'text-ink-dim',
  cyan: 'text-cyan',
  allow: 'text-allow',
  warn: 'text-warn',
  deny: 'text-deny',
};

export const toneBorder: Record<Tone, string> = {
  neutral: 'border-hairline',
  cyan: 'border-cyan/35',
  allow: 'border-allow/35',
  warn: 'border-warn/35',
  deny: 'border-deny/45',
};

export const toneBg: Record<Tone, string> = {
  neutral: 'bg-surface-2/60',
  cyan: 'bg-cyan/8',
  allow: 'bg-allow/8',
  warn: 'bg-warn/8',
  deny: 'bg-deny/10',
};

/** Maps trace/field status values onto the shared tone scale. */
export function statusTone(status?: 'pass' | 'warn' | 'fail' | 'info'): Tone {
  if (status === 'pass') return 'allow';
  if (status === 'warn') return 'warn';
  if (status === 'fail') return 'deny';
  return 'neutral';
}

/** Small mono evidence chip used for policy reasons, IDs and scores. */
export function Chip({
  children,
  tone = 'neutral',
  className = '',
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-[11px] leading-none tracking-tight ${toneBorder[tone]} ${toneBg[tone]} ${toneText[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/** Status dot. `pulse` is reserved for genuinely live indicators. */
export function Dot({ tone = 'allow', pulse = false }: { tone?: Tone; pulse?: boolean }) {
  const bg = {
    neutral: 'bg-ink-faint',
    cyan: 'bg-cyan',
    allow: 'bg-allow',
    warn: 'bg-warn',
    deny: 'bg-deny',
  }[tone];

  return (
    <span className="relative inline-flex h-2 w-2 shrink-0" aria-hidden="true">
      {pulse && (
        <span
          className={`absolute inset-0 rounded-full ${bg} opacity-60`}
          style={{ animation: 'og-pulse-ring 2.4s ease-out infinite' }}
        />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${bg}`} />
    </span>
  );
}

export function Eyebrow({ children, tone = 'cyan' }: { children: ReactNode; tone?: Tone }) {
  return (
    <p
      className={`mb-4 flex items-center gap-2.5 font-mono text-[11px] font-medium tracking-[0.18em] ${toneText[tone]}`}
    >
      <span className={`h-px w-6 ${tone === 'cyan' ? 'bg-cyan/60' : 'bg-current opacity-50'}`} />
      {children}
    </p>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  body,
  align = 'left',
  className = '',
}: {
  eyebrow?: string;
  title: ReactNode;
  body?: ReactNode;
  align?: 'left' | 'center';
  className?: string;
}) {
  return (
    <div
      className={`${align === 'center' ? 'mx-auto max-w-3xl text-center' : 'max-w-3xl'} ${className}`}
    >
      {eyebrow && (
        <p
          className={`mb-4 flex items-center gap-2.5 font-mono text-[11px] font-medium tracking-[0.18em] text-cyan ${align === 'center' ? 'justify-center' : ''}`}
        >
          <span className="h-px w-6 bg-cyan/60" />
          {eyebrow}
        </p>
      )}
      <h2 className="text-balance text-3xl font-semibold leading-[1.12] tracking-[-0.02em] text-ink sm:text-4xl lg:text-[2.75rem]">
        {title}
      </h2>
      {body && (
        <p className="mt-5 text-[15px] leading-relaxed text-ink-dim sm:text-base">{body}</p>
      )}
    </div>
  );
}

/** Consistent vertical rhythm + hairline separators between sections. */
export function Section({
  id,
  children,
  className = '',
  bleed = false,
}: {
  id?: string;
  children: ReactNode;
  className?: string;
  bleed?: boolean;
}) {
  return (
    <section
      id={id}
      className={`relative border-t border-hairline/70 py-20 sm:py-24 lg:py-28 ${className}`}
    >
      <div className={bleed ? '' : 'mx-auto w-full max-w-[1200px] px-5 sm:px-8'}>{children}</div>
    </section>
  );
}

/** Panel surface used for cards, consoles and diagram containers. */
export function Panel({
  children,
  className = '',
  tone = 'neutral',
}: {
  children: ReactNode;
  className?: string;
  tone?: Tone;
}) {
  return (
    <div
      className={`rounded-xl border bg-surface/80 ${toneBorder[tone]} ${className}`}
      style={{ backdropFilter: 'blur(2px)' }}
    >
      {children}
    </div>
  );
}
