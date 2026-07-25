import { Link } from "react-router-dom";

// One button system, used everywhere. Rules:
// - primary (gold, filled): the ONE main action of a screen.
// - secondary (outlined, fills on hover): supporting actions.
// - ghost (quiet, gains a background on hover/tap): low-stakes actions in
//   cards and rows. Never invisible until hover; mobile users have no hover.
// - danger (outlined red): opens a destructive step.
// - dangerSolid (filled red): the actual destructive confirmation. The scary
//   action must never look lighter than a safe one.

const base =
  "inline-flex items-center justify-center gap-2 font-sans font-semibold rounded-full transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed select-none whitespace-nowrap";

const sizes = {
  xs: "px-3 py-1 text-[12.5px]",
  sm: "px-3.5 py-1.5 text-[13px]",
  md: "px-5 py-2.5 text-[14px]",
  lg: "px-7 py-3 text-[15px]",
};

const variants = {
  // Disabled goes neutral rather than faded gold: dimming amber produces a
  // muddy olive that reads as broken rather than as "not ready yet".
  primary:
    "bg-amber text-void hover:bg-ambersoft shadow-[0_4px_16px_rgba(255,176,0,0.25)] disabled:bg-panel2 disabled:text-muted disabled:shadow-none disabled:opacity-100",
  secondary:
    "border border-lineb bg-transparent text-text2 hover:bg-panel2 hover:text-text",
  ghost: "text-label hover:text-text hover:bg-panel2",
  danger:
    "border border-red/60 text-red hover:bg-[rgba(255,107,129,0.1)] bg-transparent",
  dangerSolid: "bg-red text-void hover:brightness-110",
};

export function Button({
  variant = "secondary",
  size = "md",
  to,
  href,
  className = "",
  children,
  ...rest
}) {
  const cls = `${base} ${sizes[size] || sizes.md} ${variants[variant] || variants.secondary} ${className}`;
  if (to) {
    return (
      <Link to={to} className={cls} {...rest}>
        {children}
      </Link>
    );
  }
  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={cls} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  );
}
