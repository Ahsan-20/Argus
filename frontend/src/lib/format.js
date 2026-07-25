// Shared derivations and formatters. Time values derive from server
// timestamps on every read so a drifted client clock cannot lie.

// --- Watcher state ----------------------------------------------------------
// The backend stores active | paused | triggered | standby. There is no stored
// error status; errors live on the latest check. This ONE helper turns a
// watcher (+ its last check) into a display state so every dot, chip, and
// orbit color agrees.
export function probeState(watcher, lastRun) {
  const run = lastRun ?? watcher?.last_run ?? null;
  switch (watcher?.status) {
    case "triggered":
      return "TRIGGERED";
    case "paused":
      return "PAUSED";
    case "standby":
      return "STANDBY";
    default:
      if (run && run.error) return "ERROR";
      return "WATCHING";
  }
}

// Human labels. Color still never stands alone; the words carry the meaning.
export const STATE_META = {
  WATCHING: { label: "Watching", color: "var(--color-amber)", token: "amber" },
  TRIGGERED: { label: "Found it", color: "var(--color-green)", token: "green" },
  PAUSED: { label: "Paused", color: "var(--color-steel)", token: "steel" },
  STANDBY: { label: "Demo", color: "var(--color-steel)", token: "steel" },
  ERROR: { label: "Needs attention", color: "var(--color-red)", token: "red" },
};

// --- Time -------------------------------------------------------------------
export function toDate(value) {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function relativeTime(value, now = Date.now()) {
  const d = toDate(value);
  if (!d) return "never";
  const secs = Math.round((now - d.getTime()) / 1000);
  if (secs < 0) return "just now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// Time remaining until a target. Reads as words, holds at "any moment now"
// when due (checks run on a schedule, not the instant the clock hits zero).
export function countdown(target, now = Date.now()) {
  const d = toDate(target);
  if (!d) return "-";
  const total = Math.floor((d.getTime() - now) / 1000);
  if (total <= 0) return "any moment now";
  if (total < 60) return `in ${total}s`;
  const mins = Math.floor(total / 60);
  if (mins < 60) return `in ${mins} min`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem ? `in ${hrs}h ${rem}m` : `in ${hrs}h`;
}

export function absoluteTime(value) {
  const d = toDate(value);
  if (!d) return "-";
  return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
}

export function localTime(value) {
  const d = toDate(value);
  if (!d) return "-";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// --- Misc -------------------------------------------------------------------
export function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url || "the page";
  }
}

export function cadenceLabel(mins) {
  if (mins == null) return "-";
  if (mins < 60) return `${mins} minutes`;
  if (mins === 60) return "hour";
  if (mins % 60 === 0) return `${mins / 60} hours`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

// Trim noisy precision off a tracked value for display. An exchange rate
// arrives as "277.932811", of which only "277.93" carries meaning. Anything
// that is not a bare number is left exactly as the page wrote it, so "3 slots",
// "Rs. 412,000" and "Aug 15, 2026" pass through untouched.
export function compactValue(value) {
  const s = String(value ?? "").trim();
  if (!s || !/^-?[\d,]+(\.\d+)?$/.test(s)) return s;
  const n = parseFloat(s.replace(/,/g, ""));
  if (!Number.isFinite(n)) return s;
  const magnitude = Math.abs(n);
  const places = magnitude >= 100 ? 2 : magnitude >= 1 ? 3 : 6;
  return Number(n.toFixed(places)).toLocaleString(undefined, {
    maximumFractionDigits: places,
  });
}

export function truncate(text, n = 80) {
  const t = (text || "").trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

export function verdictLabel(run) {
  if (!run) return "No checks yet";
  if (run.error) return "Couldn't read the page";
  if (run.verdict_met === true) return "Found it";
  if (run.verdict_met === false) return "Not yet";
  return "-";
}
