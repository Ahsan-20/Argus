import { STATE_META } from "../lib/format.js";

// Status chip: a soft rounded pill with a dot and a plain word. The word, not
// the color, carries the meaning.

export function StatusDot({ state = "WATCHING", pulse = false, size = 8 }) {
  const meta = STATE_META[state] || STATE_META.WATCHING;
  return (
    <span className="relative inline-flex" aria-hidden="true">
      <span
        className="inline-block rounded-full"
        style={{ width: size, height: size, backgroundColor: meta.color }}
      />
      {pulse && (
        <span
          className="absolute inset-0 inline-block animate-ping rounded-full"
          style={{ backgroundColor: meta.color, opacity: 0.6 }}
        />
      )}
    </span>
  );
}

export function StatusPill({ state = "WATCHING", className = "" }) {
  const meta = STATE_META[state] || STATE_META.WATCHING;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-semibold ${className}`}
      style={{
        borderColor: `color-mix(in srgb, ${meta.color} 45%, transparent)`,
        color: meta.color,
        background: `color-mix(in srgb, ${meta.color} 10%, transparent)`,
      }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: meta.color }}
      />
      {meta.label}
    </span>
  );
}
