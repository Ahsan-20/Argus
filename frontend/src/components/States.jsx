import { Button } from "./Button.jsx";

// Loading, empty, and error states in plain language.

export function Loading({ label = "Checking…", bar = true, className = "" }) {
  return (
    <div className={`flex flex-col items-start gap-3 ${className}`}>
      <span className="text-[14px] text-label">{label}</span>
      {bar && (
        <span className="relative block h-[4px] w-40 overflow-hidden rounded-full bg-line telemetry-sweep" />
      )}
    </div>
  );
}

export function Skeleton({ lines = 3 }) {
  return (
    <div className="flex flex-col gap-2" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <span
          key={i}
          className="relative block h-3 overflow-hidden rounded-full bg-panel2 telemetry-sweep"
          style={{ width: `${70 - i * 10}%` }}
        />
      ))}
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  message = "",
  action,
  className = "",
}) {
  return (
    <div className={`flex flex-col items-center gap-2 py-12 text-center ${className}`}>
      <p className="font-display text-[18px] font-semibold text-text">{title}</p>
      {message && <p className="text-[14px] text-muted">{message}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className = "" }) {
  const message =
    (error && (error.detail || error.message)) || "Something went wrong.";
  return (
    <div
      className={`flex flex-col items-start gap-3 rounded-xl border border-red/50 bg-[rgba(255,107,129,0.06)] p-4 ${className}`}
      role="alert"
    >
      <p className="text-[14px] font-semibold text-red">Couldn't load this</p>
      <p className="text-[14px] text-text2">{message}</p>
      {onRetry && (
        <Button variant="danger" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
