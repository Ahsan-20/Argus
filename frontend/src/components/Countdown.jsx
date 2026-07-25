import { useEffect, useState } from "react";
import { countdown } from "../lib/format.js";

// "Next check in 7 min", ticking locally, resynced from the server timestamp
// on every poll. Reads as words and never goes negative.
// `quiet` keeps the imminent-check highlight off. Going gold for "any moment
// now" reads as urgency, which is right on a single watcher's page but wrong
// in a list, where half the cards say it at once and the colour ends up
// pointing at the least interesting thing on screen.
export function Countdown({ target, className = "", prefix = "", quiet = false }) {
  const [, force] = useState(0);
  useEffect(() => {
    const t = setInterval(() => force((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const value = countdown(target);
  return (
    <span
      className={`tnum ${className}`}
      style={
        value === "any moment now" && !quiet
          ? { color: "var(--color-amber)" }
          : undefined
      }
    >
      {prefix}
      {value}
    </span>
  );
}
