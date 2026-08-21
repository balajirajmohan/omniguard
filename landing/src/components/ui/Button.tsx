import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router-dom';

type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

const base =
  'inline-flex items-center justify-center gap-2 rounded-md font-medium tracking-tight ' +
  'cursor-pointer select-none whitespace-nowrap ' +
  'transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-out ' +
  'active:translate-y-px disabled:pointer-events-none disabled:opacity-50';

const variants: Record<Variant, string> = {
  primary:
    'bg-cyan text-graphite border border-cyan-bright/50 ' +
    'shadow-[0_0_0_1px_rgba(34,211,238,0.15),0_8px_24px_-10px_rgba(34,211,238,0.7)] ' +
    'hover:bg-cyan-bright hover:shadow-[0_0_0_1px_rgba(103,232,249,0.3),0_10px_30px_-8px_rgba(34,211,238,0.85)]',
  secondary:
    'border border-hairline-strong bg-surface-2/60 text-ink ' +
    'hover:border-cyan/50 hover:bg-surface-3/70 hover:text-cyan-bright',
  ghost: 'text-ink-dim hover:text-ink hover:bg-surface-2/60 border border-transparent',
};

const sizes: Record<Size, string> = {
  sm: 'h-9 px-3.5 text-[13px]',
  md: 'h-11 px-5 text-sm',
  lg: 'h-12 px-6 text-[15px]',
};

interface CommonProps {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...rest
}: CommonProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export function ButtonLink({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  href,
  ...rest
}: CommonProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const cls = `${base} ${variants[variant]} ${sizes[size]} ${className}`;

  // Internal routes go through the router; hash links stay native for smooth scroll.
  if (href.startsWith('/') && !href.startsWith('//')) {
    return (
      <Link to={href} className={cls}>
        {children}
      </Link>
    );
  }

  return (
    <a href={href} className={cls} {...rest}>
      {children}
    </a>
  );
}

export function ArrowRight({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M3 8h10m0 0-4-4m4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
