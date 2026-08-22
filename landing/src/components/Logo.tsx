/**
 * OmniGuard mark: a shield built from a hexagon, with a robot motion path
 * traced through it: identity boundary + movement in one glyph.
 */
export function LogoMark({ size = 28, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M16 2.5 27.5 8.5v9.2c0 6.1-4.6 10.6-11.5 12.8C9.1 28.3 4.5 23.8 4.5 17.7V8.5L16 2.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        className="text-cyan"
      />
      <path
        d="M4.5 8.5 16 14.4l11.5-5.9"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinejoin="round"
        className="text-cyan/35"
      />
      {/* Motion path through the boundary. */}
      <path
        d="M9.5 21.5c3.2 0 3.4-6 6.5-6s3.3 6 6.5 6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        className="text-cyan-bright"
      />
      <circle cx="16" cy="15.5" r="1.9" fill="currentColor" className="text-cyan-bright" />
    </svg>
  );
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span
      className={`text-[17px] font-semibold tracking-[-0.02em] text-ink ${className}`}
    >
      Omni<span className="text-cyan">Guard</span>
    </span>
  );
}
