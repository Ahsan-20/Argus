// The Argus mark, inline SVG so it needs no asset fetch and inherits currentColor
// (amber). An all-seeing eye inside an orbital ring with a probe on it.
export function Logo({ size = 30, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      role="img"
      aria-label="Argus"
    >
      <ellipse
        cx="20"
        cy="20"
        rx="17"
        ry="9"
        stroke="var(--color-amber)"
        strokeWidth="1.2"
        transform="rotate(-22 20 20)"
        opacity="0.7"
      />
      <circle cx="20" cy="20" r="8.5" stroke="var(--color-amber)" strokeWidth="1.4" />
      <circle cx="20" cy="20" r="3.4" fill="var(--color-amber)" />
      {/* the probe riding the orbit ring */}
      <circle cx="35" cy="13.8" r="2" fill="var(--color-amber)" />
    </svg>
  );
}

export function Wordmark({ className = "" }) {
  return (
    <span
      className={`font-display font-bold tracking-[0.32em] text-text ${className}`}
    >
      ARGUS
    </span>
  );
}
