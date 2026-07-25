// Soft rounded card. Depth comes from a gentle shadow and a hairline border.
// Kept the Panel name so existing imports work; Bracket is retired and renders
// nothing (the HUD look is gone on purpose).

export function Bracket() {
  return null;
}

export function Panel({
  title,
  actions,
  children,
  className = "",
  bodyClass = "",
  as: Tag = "section",
}) {
  return (
    <Tag
      className={`rounded-2xl border border-line bg-panel ${className}`}
      style={{ boxShadow: "var(--card-shadow)" }}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 px-5 pt-4 pb-1">
          {title && (
            <h3 className="font-display text-[15px] font-semibold text-text">
              {title}
            </h3>
          )}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={`p-5 ${title || actions ? "pt-3" : ""} ${bodyClass}`}>
        {children}
      </div>
    </Tag>
  );
}
