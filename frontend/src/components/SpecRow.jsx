// A labelled fact with a glyph. Shared so the watcher page and settings read
// as the same product.
//
// The label sits above the value rather than beside it: in a narrow card a
// two-column row leaves both halves cramped, which is what makes long values
// wrap into a mess.

export const GLYPH = {
  clock: (
    <>
      <circle cx="9" cy="9" r="6.6" stroke="currentColor" strokeWidth="1.4" fill="none" />
      <path d="M9 5.4V9l2.6 1.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none" />
    </>
  ),
  track: (
    <path
      d="M2.4 12.6 6.4 8l3 2.6 4.4-5.4"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
      strokeLinejoin="round" fill="none"
    />
  ),
  bell: (
    <>
      <path
        d="M4.8 12.2v-3.6a4.2 4.2 0 0 1 8.4 0v3.6l1.2 1.6H3.6l1.2-1.6Z"
        stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none"
      />
      <path d="M7.4 15.4a1.7 1.7 0 0 0 3.2 0" stroke="currentColor" strokeWidth="1.4" fill="none" />
    </>
  ),
  mail: (
    <>
      <rect x="2.4" y="4.4" width="13.2" height="9.2" rx="1.6" stroke="currentColor" strokeWidth="1.4" fill="none" />
      <path d="m3 5.6 6 4.2 6-4.2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none" />
    </>
  ),
  flag: (
    <>
      <path d="M4.6 15.4V3.2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M4.6 3.8h8.2l-1.7 2.7 1.7 2.7H4.6" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none" />
    </>
  ),
  chat: (
    <path
      d="M15.4 8.6c0 3-2.9 5.4-6.4 5.4a7.6 7.6 0 0 1-2-.26L3.4 15l.9-2.7A5 5 0 0 1 2.6 8.6c0-3 2.9-5.4 6.4-5.4s6.4 2.4 6.4 5.4Z"
      stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none"
    />
  ),
  orbit: (
    <>
      <circle cx="9" cy="9" r="4.4" stroke="currentColor" strokeWidth="1.4" fill="none" />
      <ellipse cx="9" cy="9" rx="7.6" ry="3.4" stroke="currentColor" strokeWidth="1.3" fill="none" transform="rotate(-24 9 9)" />
    </>
  ),
  pulse: (
    <path
      d="M1.6 9h3L6.6 4.4l3.4 8.8 1.8-4.2h3.6"
      stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
      strokeLinejoin="round" fill="none"
    />
  ),
  tag: (
    <>
      <path d="M8.4 2.6H15.4V9.6l-6.6 6.6-6.4-6.4 6-7.2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none" />
      <circle cx="12" cy="6" r="1.2" fill="currentColor" />
    </>
  ),
};

export function SpecRow({ icon, label, value, note, highlight, tone }) {
  const color = tone || (highlight ? "var(--color-amber)" : "var(--color-muted)");
  return (
    <div className="flex gap-3 border-t border-line px-4 py-3 first:border-t-0">
      <span className="mt-0.5 shrink-0" style={{ color }} aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 18 18">{icon}</svg>
      </span>
      <div className="min-w-0">
        <p className="text-[11.5px] font-semibold uppercase tracking-wide text-muted">
          {label}
        </p>
        <p
          className="mt-0.5 break-words text-[14px] leading-snug"
          style={{
            color: tone || (highlight ? "var(--color-amber)" : "var(--color-text2)"),
            fontWeight: highlight || tone ? 600 : 400,
          }}
        >
          {value}
        </p>
        {/* break-words matters here: notes carry email addresses, which are
            long unbroken strings that would otherwise push past the card. */}
        {note && (
          <p className="mt-1 break-words text-[12px] leading-relaxed text-muted">
            {note}
          </p>
        )}
      </div>
    </div>
  );
}

// Wraps rows so they run full bleed inside a Panel's padding.
export function SpecList({ children }) {
  return <div className="-mx-5 -mt-1 border-y border-line">{children}</div>;
}
