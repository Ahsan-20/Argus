import { relativeTime } from "../lib/format.js";

// One friendly summary line under the top bar. No jargon, no marquee.
export function TelemetryTicker({ stats, fleetCount }) {
  if (!stats) return null;

  const by = stats.by_status || {};
  const watching = by.active || 0;
  const found = by.triggered || 0;
  const count = fleetCount ?? stats.total_watchers ?? 0;

  const parts = [];
  parts.push(`${count} watcher${count === 1 ? "" : "s"}`);
  if (watching) parts.push(`${watching} on duty`);
  if (found) parts.push(`${found} found what they were looking for`);
  if (stats.last_run_at) parts.push(`last check ${relativeTime(stats.last_run_at)}`);

  return (
    <div className="border-b border-line bg-panel/60 px-4 py-2">
      <span className="mx-auto block max-w-[1200px] text-[13px] text-label">
        {parts.join(" · ")}
      </span>
    </div>
  );
}
