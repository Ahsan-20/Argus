import { useMemo } from "react";
import { probeState, STATE_META } from "../lib/format.js";
import { usePrefs } from "../state/prefs.jsx";

// The living sky, v3. Deterministic: rings are check-frequency bands and each
// watcher's starting angle is seeded from its id, so the layout never
// shuffles between visits. Decorative and aria-hidden; the list is the
// accessible source of truth.
//
// Realism, all CSS/SVG:
// - depth: dots grow/brighten on the near side of the orbit, shrink/dim on
//   the far side, synced to the rotation clock via matching duration/delay
// - comet trails that fade along their length (three arc segments)
// - a gradient-bloom core around the watchful eye, softly breathing
// - a double radar pulse (ring + echo)
// - the in-scene stars wheel slowly around the center, long-exposure style
// Under reduced motion everything freezes legible; pulses stay invisible.

const SIZE = 400;
const C = SIZE / 2;
const RINGS = [58, 96, 134, 172];

// In-scene twinkles: [x, y, delaySeconds]
const SCENE_TWINKLES = [
  [42, 58, 0],
  [352, 44, 1.3],
  [372, 214, 2.4],
  [56, 336, 0.8],
  [214, 20, 1.9],
  [332, 352, 3.1],
  [20, 198, 2.7],
  [140, 372, 3.6],
];

function bandOf(cadence) {
  if (cadence <= 30) return 0;
  if (cadence <= 120) return 1;
  if (cadence <= 480) return 2;
  return 3;
}

function periodOf(cadence) {
  const c = Math.max(15, Math.min(1440, cadence || 30));
  const t = (c - 15) / (1440 - 15);
  return 14 + t * (80 - 14); // seconds per revolution
}

function seedAngle(id) {
  return ((id * 137.5) % 360) * (Math.PI / 180); // golden-angle spread
}

// One arc segment of the orbit between two trailing angles (degrees behind
// the dot). Used to build a tail that fades along its length.
function arcSeg(r, fromDeg, toDeg) {
  const a1 = (-fromDeg * Math.PI) / 180;
  const a2 = (-toDeg * Math.PI) / 180;
  return (
    `M ${C + r * Math.cos(a1)} ${C + r * Math.sin(a1)} ` +
    `A ${r} ${r} 0 0 1 ${C + r * Math.cos(a2)} ${C + r * Math.sin(a2)}`
  );
}

const TAIL = [
  { from: 30, to: 18, opacity: 0.1, width: 1.4 },
  { from: 18, to: 8, opacity: 0.24, width: 2 },
  { from: 8, to: 0, opacity: 0.45, width: 2.6 },
];

export function OrbitMap({
  watchers = [],
  onSelect,
  callsign = "you",
  compact = false,
  pinging = false,
}) {
  const { reducedMotion } = usePrefs();

  const probes = useMemo(
    () =>
      watchers.map((w) => {
        const state = probeState(w);
        const band = bandOf(w.cadence_minutes);
        const r = RINGS[band];
        const period = periodOf(w.cadence_minutes);
        const a = seedAngle(w.id);
        const start = ((w.id * 137.5) % 360) / 360;
        return {
          id: w.id,
          callsign: w.callsign,
          color: STATE_META[state].color,
          triggered: state === "TRIGGERED",
          r,
          period,
          x: C + r * Math.cos(a),
          y: C + r * Math.sin(a),
          delay: -start * period,
        };
      }),
    [watchers],
  );

  const usedRings = [...new Set(probes.map((p) => p.r))];
  const rings = usedRings.length ? usedRings : RINGS.slice(0, 2);
  const outer = Math.max(...rings);

  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className={`h-full w-full ${onSelect ? "orbit-clickable" : ""}`}
      aria-hidden="true"
      style={{ maxHeight: compact ? 300 : 560 }}
    >
      <defs>
        {/* real light falloff for the core bloom */}
        <radialGradient id="coreBloom" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--color-amber)" stopOpacity="0.5" />
          <stop offset="45%" stopColor="var(--color-amber)" stopOpacity="0.14" />
          <stop offset="100%" stopColor="var(--color-amber)" stopOpacity="0" />
        </radialGradient>
        {/* subtle sphere shading for the core body */}
        <radialGradient id="coreSphere" cx="38%" cy="32%" r="80%">
          <stop offset="0%" stopColor="#2a3352" />
          <stop offset="100%" stopColor="#101527" />
        </radialGradient>
      </defs>

      {/* the heavens wheel slowly behind the orbits */}
      {reducedMotion ? (
        <g>
          {SCENE_TWINKLES.map(([x, y, d]) => (
            <circle
              key={`${x}-${y}`}
              cx={x}
              cy={y}
              r="1.2"
              fill="#fff"
              className="scene-twinkle"
              style={{ animationDelay: `${d}s` }}
            />
          ))}
        </g>
      ) : (
        <g className="orbit-ring" style={{ animationDuration: "360s" }}>
          {SCENE_TWINKLES.map(([x, y, d]) => (
            <circle
              key={`${x}-${y}`}
              cx={x}
              cy={y}
              r="1.2"
              fill="#fff"
              className="scene-twinkle"
              style={{ animationDelay: `${d}s` }}
            />
          ))}
        </g>
      )}

      {/* orbit rings */}
      {rings.map((r) => (
        <circle
          key={r}
          cx={C}
          cy={C}
          r={r}
          fill="none"
          stroke="var(--color-line)"
          strokeWidth="1"
        />
      ))}

      {/* the quiet radar pulse and its echo */}
      <circle
        className="orbit-autoping"
        cx={C}
        cy={C}
        r={outer}
        fill="none"
        stroke="var(--color-amber)"
        strokeWidth="1.2"
      />
      <circle
        className="orbit-autoping"
        cx={C}
        cy={C}
        r={outer}
        fill="none"
        stroke="var(--color-amber)"
        strokeWidth="0.8"
        style={{ animationDelay: "0.45s" }}
      />

      {/* a stronger ping on demand (demo) */}
      {pinging && (
        <circle
          className="radar-ping"
          cx={C}
          cy={C}
          r={outer}
          fill="none"
          stroke="var(--color-amber)"
          strokeWidth="1.5"
        />
      )}

      {/* the core: gradient bloom breathing around a shaded sphere + the eye */}
      <circle cx={C} cy={C} r="52" fill="url(#coreBloom)" className="core-breathe" />
      <circle
        cx={C}
        cy={C}
        r="19"
        fill="url(#coreSphere)"
        stroke="var(--color-lineb)"
      />
      <ellipse
        cx={C}
        cy={C}
        rx="10.5"
        ry="6.5"
        fill="none"
        stroke="var(--color-amber)"
        strokeWidth="1.4"
      />
      <circle cx={C} cy={C} r="3.2" fill="var(--color-amber)" />
      {!compact && (
        <text
          x={C}
          y={C + 36}
          textAnchor="middle"
          fontSize="10.5"
          fontWeight="600"
          letterSpacing="0.5"
          fill="var(--color-label)"
          fontFamily="var(--font-sans)"
        >
          {callsign}
        </text>
      )}

      {/* watchers */}
      {probes.map((p) => {
        const dot = (
          <>
            {p.triggered && (
              <circle r="9" fill="none" stroke={p.color} strokeWidth="1" opacity="0.5">
                <animate
                  attributeName="r"
                  values="6;12;6"
                  dur="2s"
                  repeatCount="indefinite"
                />
              </circle>
            )}
            {/* layered halo glow */}
            <circle r={compact ? 9 : 11} fill={p.color} opacity="0.07" />
            <circle r={compact ? 6 : 7.5} fill={p.color} opacity="0.16" />
            <circle
              r={compact ? 3.5 : 4.5}
              fill={p.color}
              style={{ cursor: onSelect ? "pointer" : "default" }}
              onClick={() => onSelect?.(p.id)}
            />
            {/* generous invisible hit target: a moving 4px dot is a cruel
                thing to ask a finger to hit */}
            {onSelect && (
              <circle
                r="16"
                fill="transparent"
                style={{ cursor: "pointer" }}
                onClick={() => onSelect(p.id)}
              >
                <title>{p.callsign}</title>
              </circle>
            )}
            {!compact && (
              <text
                x="12"
                y="3.5"
                fontSize="9"
                fontWeight="500"
                fill="var(--color-text2)"
                fontFamily="var(--font-sans)"
                style={{ cursor: onSelect ? "pointer" : "default" }}
                onClick={() => onSelect?.(p.id)}
              >
                {p.callsign}
              </text>
            )}
          </>
        );

        if (reducedMotion) {
          // Frozen at a legible seeded arrangement.
          return (
            <g key={p.id} transform={`translate(${p.x} ${p.y})`}>
              {dot}
            </g>
          );
        }

        const clock = {
          animationDuration: `${p.period}s`,
          animationDelay: `${p.delay}s`,
        };

        return (
          <g key={p.id} className="orbit-ring" style={clock}>
            {/* comet tail, fading along its length */}
            {TAIL.map((seg) => (
              <path
                key={seg.from}
                d={arcSeg(p.r, seg.from, seg.to)}
                fill="none"
                stroke={p.color}
                strokeWidth={seg.width}
                strokeLinecap="round"
                opacity={seg.opacity}
              />
            ))}
            <g transform={`translate(${C + p.r} ${C})`}>
              {/* counter-rotation keeps the label upright; the depth clock
                  breathes size and brightness as the dot rounds the orbit */}
              <g className="orbit-label" style={clock}>
                <g className="orbit-depth" style={clock}>
                  {dot}
                </g>
              </g>
            </g>
          </g>
        );
      })}
    </svg>
  );
}
