import { useEffect, useState } from "react";
import { usePrefs } from "../state/prefs.jsx";

// What the watcher is doing, drawn rather than described.
//
// The ring is a real clock: it fills as the wait toward the next check runs
// down, so a glance tells you whether the next look is imminent or hours off.
// The eye in the middle carries the state. It blinks while waiting, opens
// wide and sweeps while checking, closes when paused, and goes still when the
// thing has been found. Everything freezes under reduced motion.

const SIZE = 132;
const C = SIZE / 2;
const R = 52;
const CIRC = 2 * Math.PI * R;

const LOOK = {
  WATCHING: { ring: "var(--color-amber)", eye: "var(--color-amber)" },
  TRIGGERED: { ring: "var(--color-green)", eye: "var(--color-green)" },
  PAUSED: { ring: "var(--color-steel)", eye: "var(--color-steel)" },
  STANDBY: { ring: "var(--color-steel)", eye: "var(--color-steel)" },
  ERROR: { ring: "var(--color-red)", eye: "var(--color-red)" },
};

export function WatchDial({ state = "WATCHING", nextRunAt, cadenceMinutes, checking = false }) {
  const { reducedMotion } = usePrefs();
  const [, tick] = useState(0);

  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const look = LOOK[state] || LOOK.WATCHING;
  const paused = state === "PAUSED" || state === "STANDBY";
  const found = state === "TRIGGERED";

  // How far through the wait we are. The cycle is assumed to have started one
  // cadence before the next check is due, which is exactly how the scheduler
  // sets it.
  let progress = 0;
  const next = nextRunAt ? new Date(nextRunAt).getTime() : null;
  const period = (cadenceMinutes || 60) * 60_000;
  if (next && !paused && !found) {
    const elapsed = period - (next - Date.now());
    progress = Math.max(0, Math.min(1, elapsed / period));
  }
  if (found) progress = 1;

  const dash = CIRC * progress;
  // The dot that rides the ring sits at the head of the filled arc.
  const angle = -Math.PI / 2 + progress * 2 * Math.PI;
  const dotX = C + R * Math.cos(angle);
  const dotY = C + R * Math.sin(angle);

  const animate = !reducedMotion;
  const nearly = progress > 0.9 && !paused && !found;

  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="img"
      aria-label={
        checking
          ? "Checking the page now"
          : paused
            ? "Paused"
            : found
              ? "Found what it was looking for"
              : `${Math.round(progress * 100)} percent of the way to the next check`
      }
    >
      <defs>
        <radialGradient id="dialGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={look.eye} stopOpacity={checking ? 0.35 : 0.18} />
          <stop offset="70%" stopColor={look.eye} stopOpacity="0.04" />
          <stop offset="100%" stopColor={look.eye} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* the glow behind everything, breathing while on duty */}
      <circle
        cx={C}
        cy={C}
        r={R - 4}
        fill="url(#dialGlow)"
        className={animate && !paused ? "core-breathe" : undefined}
      />

      {/* the track the wait runs along */}
      <circle cx={C} cy={C} r={R} fill="none" stroke="var(--color-line)" strokeWidth="3" />

      {/* how far through the wait we are */}
      {!paused && (
        <circle
          cx={C}
          cy={C}
          r={R}
          fill="none"
          stroke={look.ring}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${CIRC}`}
          transform={`rotate(-90 ${C} ${C})`}
          opacity={found ? 1 : 0.9}
          style={{ transition: "stroke-dasharray 1s linear" }}
        />
      )}

      {/* the head of the arc, brighter when the next look is imminent */}
      {!paused && !found && progress > 0.01 && (
        <circle cx={dotX} cy={dotY} r={nearly ? 5 : 3.5} fill={look.ring}>
          {animate && nearly && (
            <animate attributeName="r" values="3.5;6;3.5" dur="1s" repeatCount="indefinite" />
          )}
        </circle>
      )}

      {/* a sweep hand while a check is actually running */}
      {checking && animate && (
        <g className="orbit-ring" style={{ animationDuration: "1.4s" }}>
          <line
            x1={C}
            y1={C}
            x2={C}
            y2={C - R}
            stroke={look.ring}
            strokeWidth="2"
            strokeLinecap="round"
            opacity="0.7"
          />
        </g>
      )}

      {/* the eye */}
      {paused ? (
        // closed: a lid, and lashes, plainly asleep
        <>
          <path
            d={`M ${C - 16} ${C} q 16 11 32 0`}
            fill="none"
            stroke={look.eye}
            strokeWidth="2.4"
            strokeLinecap="round"
          />
          <line x1={C - 13} y1={C + 6} x2={C - 16} y2={C + 10} stroke={look.eye} strokeWidth="1.8" strokeLinecap="round" />
          <line x1={C} y1={C + 8} x2={C} y2={C + 12} stroke={look.eye} strokeWidth="1.8" strokeLinecap="round" />
          <line x1={C + 13} y1={C + 6} x2={C + 16} y2={C + 10} stroke={look.eye} strokeWidth="1.8" strokeLinecap="round" />
        </>
      ) : (
        <>
          <ellipse
            cx={C}
            cy={C}
            rx={checking ? 19 : 16}
            ry={checking ? 12 : 10}
            fill="none"
            stroke={look.eye}
            strokeWidth="2.2"
            style={{ transition: "all 300ms var(--ease-ui)" }}
          >
            {animate && !checking && !found && (
              // a blink: the lid drops for a moment every few seconds
              <animate
                attributeName="ry"
                values="10;10;1;10;10"
                keyTimes="0;0.86;0.9;0.94;1"
                dur="6s"
                repeatCount="indefinite"
              />
            )}
          </ellipse>
          <circle cx={C} cy={C} r={checking ? 6 : 5} fill={look.eye}>
            {animate && checking && (
              <animate attributeName="r" values="5;7;5" dur="0.9s" repeatCount="indefinite" />
            )}
          </circle>
          {found && (
            <circle cx={C} cy={C} r="13" fill="none" stroke={look.eye} strokeWidth="1.4" opacity="0.5">
              {animate && (
                <animate attributeName="r" values="11;17;11" dur="2.4s" repeatCount="indefinite" />
              )}
            </circle>
          )}
        </>
      )}
    </svg>
  );
}
