import { relativeTime } from "../lib/format.js";

// One friendly summary line under the top bar. No jargon, no marquee.
export function TelemetryTicker({ stats, fleetCount, offline }) {
  if (offline) {
    // Deliberately not alarming, and not red. The overwhelmingly common cause
    // is the service having gone to sleep after a quiet spell, which takes up
    // to a minute to undo and fixes itself. Saying "can't reach Argus" in red
    // for something that is merely slow teaches people to distrust the app at
    // the exact moment nothing is actually wrong.
    return (
      <div className="border-b border-line bg-panel/60 px-4 py-2">
        <span className="mx-auto block max-w-[1200px] text-[13px] text-label">
          Reconnecting to Argus. If it has been idle a while it can take up to a
          minute to wake up. Your watchers keep running and nothing is lost.
        </span>
      </div>
    );
  }
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
