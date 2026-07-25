import { localTime } from "../lib/format.js";

// Inline SVG trend visuals. No chart library.

function parseNum(v) {
  return typeof v === "number"
    ? v
    : parseFloat(String(v).replace(/[^0-9.-]/g, ""));
}

// Tiny inline line for tight spots.
export function Sparkline({ values = [], width = 220, height = 44, className = "" }) {
  const nums = values.map(parseNum).filter((n) => Number.isFinite(n));
  if (nums.length < 2) return null;

  const min = Math.min(...nums);
  const max = Math.max(...nums);
  // Same honesty rule as TrendChart: never zoom so far in that a trivial
  // wobble looks like a swing.
  const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
  const span = Math.max(max - min, Math.abs(mean) * 0.02) || 1;
  const mid = (min + max) / 2;
  const lo = mid - span / 2;
  const pad = 4;
  const stepX = (width - pad * 2) / (nums.length - 1);
  const y = (n) => height - pad - ((n - lo) / span) * (height - pad * 2);
  const pts = nums.map((n, i) => `${pad + i * stepX},${y(n)}`);
  const last = pts[pts.length - 1].split(",");

  return (
    <svg
      className={className}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Trend of ${nums.length} values, latest ${nums[nums.length - 1]}`}
    >
      <path
        d={`M ${pts.join(" L ")}`}
        fill="none"
        stroke="var(--color-amber)"
        strokeWidth="1.5"
      />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill="var(--color-amber)" />
    </svg>
  );
}

// Trim a number to a sensible number of decimals for reading.
function fmt(n) {
  const a = Math.abs(n);
  const places = a >= 100 ? 2 : a >= 1 ? 3 : 6;
  return Number(n.toFixed(places)).toString();
}

// Full-width trend chart for the details page. points: [{ value, at }],
// oldest first. Falls back to null when fewer than two numeric points.
export function TrendChart({ points = [], className = "" }) {
  const data = points
    .map((p) => ({ ...p, n: parseNum(p.value) }))
    .filter((p) => Number.isFinite(p.n));
  if (data.length < 2) return null;

  const W = 600;
  const H = 150;
  const pad = 12;
  const values = data.map((p) => p.n);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;

  // A chart that auto-zooms to its own data tells lies about small numbers: a
  // rate wobbling by 0.00007 would fill the full height and read as a crash.
  // The visible range is therefore never allowed to be narrower than a couple
  // of percent of the value itself, so a small move draws small and a value
  // that has not really moved draws flat, which is the truth.
  const spanFloor = Math.abs(mean) * 0.02;
  const realSpan = max - min;
  const span = Math.max(realSpan, spanFloor) || 1;
  const mid = (min + max) / 2;
  const lo = mid - span / 2;
  const flat = realSpan <= spanFloor * 0.15;

  const x = (i) => pad + (i * (W - pad * 2)) / (data.length - 1);
  const y = (n) => H - pad - ((n - lo) / span) * (H - pad * 2);
  const pts = data.map((p, i) => `${x(i)},${y(p.n)}`);
  const line = `M ${pts.join(" L ")}`;
  const area = `${line} L ${x(data.length - 1)},${H - pad} L ${x(0)},${H - pad} Z`;
  const first = data[0];
  const last = data[data.length - 1];

  const delta = last.n - first.n;
  const pct = first.n ? (delta / Math.abs(first.n)) * 100 : 0;
  const change = flat
    ? "barely moved so far"
    : `${delta > 0 ? "up" : "down"} ${fmt(Math.abs(delta))} (${Math.abs(pct).toFixed(2)}%)`;

  return (
    <figure className={className}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="h-[150px] w-full"
        role="img"
        aria-label={`${data.length} recorded values, ${change}, now ${last.value}`}
      >
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-amber)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--color-amber)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* High and low guides only earn their place once they differ. */}
        {!flat && (
          <>
            <line
              x1={pad} x2={W - pad} y1={y(max)} y2={y(max)}
              stroke="var(--color-line)" strokeDasharray="3 5" strokeWidth="1"
            />
            <line
              x1={pad} x2={W - pad} y1={y(min)} y2={y(min)}
              stroke="var(--color-line)" strokeDasharray="3 5" strokeWidth="1"
            />
          </>
        )}
        <path d={area} fill="url(#trendFill)" />
        <path
          d={line}
          fill="none"
          stroke="var(--color-amber)"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        <circle cx={x(data.length - 1)} cy={y(last.n)} r="3.5" fill="var(--color-amber)" />
      </svg>
      <figcaption className="mt-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-[12px] text-muted">
          {localTime(first.at)} · {first.value}
        </span>
        <span className={`text-[12px] ${flat ? "text-muted" : "text-text2"}`}>
          {change}
          {!flat && ` · high ${fmt(max)} · low ${fmt(min)}`}
        </span>
        <span className="text-[13px] font-semibold text-amber">
          now {last.value}
        </span>
      </figcaption>
    </figure>
  );
}
