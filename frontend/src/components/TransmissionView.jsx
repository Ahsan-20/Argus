import { Logo } from "./Logo.jsx";
import { localTime } from "../lib/format.js";

// The alert rendered the way it landed in the inbox: sender, recipient,
// time, subject, body. Stored in-app so it is never lost to a spam filter.
export function TransmissionView({ payload, stamp }) {
  if (!payload) return null;
  const channels = payload.channels || {};

  return (
    <div className="min-w-0 overflow-hidden rounded-xl border border-line bg-panel2">
      {/* mail header: who, to whom, when */}
      <div className="flex items-start gap-3 border-b border-line px-4 py-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--amber-fill)]">
          <Logo size={20} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <span className="truncate text-[13.5px] font-semibold text-text">
              Argus Mission Control
            </span>
            {stamp && (
              <span className="shrink-0 text-[12px] text-muted">
                {localTime(stamp)}
              </span>
            )}
          </div>
          {payload.to && (
            <p className="truncate text-[12px] text-muted" title={payload.to}>
              to {payload.to}
            </p>
          )}
        </div>
      </div>

      {/* the mail itself */}
      <div className="px-4 py-3.5 sm:px-5">
        <p className="font-display text-[15.5px] font-semibold leading-snug text-text">
          {payload.subject}
        </p>
        <p className="mt-2 whitespace-pre-wrap break-words text-[13.5px] leading-relaxed text-text2">
          {payload.body}
        </p>
        <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
          {Object.entries(channels).map(([name, res]) => (
            <span
              key={name}
              className="rounded-full border px-2 py-0.5 text-[11.5px] font-medium capitalize"
              style={{
                borderColor: res?.sent
                  ? "color-mix(in srgb, var(--color-green) 50%, transparent)"
                  : "var(--color-line)",
                color: res?.sent ? "var(--color-green)" : "var(--color-muted)",
              }}
              title={res?.note || res?.error || ""}
            >
              {name}: {res?.sent ? "delivered" : "not sent"}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
