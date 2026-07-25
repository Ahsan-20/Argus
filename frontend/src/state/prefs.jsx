import { createContext, useContext, useEffect, useMemo, useState } from "react";

// Display preferences (plan s.5.3, s.4.4). Reduced motion and the texture
// toggle persist across sessions and are applied as data-attributes on <html>,
// which the CSS keys off. Reduced motion defaults to the OS setting.

const PrefsContext = createContext(null);
const MOTION_KEY = "argus.pref.motion"; // "reduce" | "full" | null(system)
const TEXTURE_KEY = "argus.pref.texture"; // "on" | "off"

function systemReducedMotion() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function PrefsProvider({ children }) {
  const [motionPref, setMotionPref] = useState(
    () => localStorage.getItem(MOTION_KEY) || "system",
  );
  const [texture, setTexture] = useState(
    () => (localStorage.getItem(TEXTURE_KEY) || "on") === "on",
  );

  const reducedMotion =
    motionPref === "reduce" || (motionPref === "system" && systemReducedMotion());

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-motion", reducedMotion ? "reduce" : "full");
    root.setAttribute("data-texture", texture ? "on" : "off");
  }, [reducedMotion, texture]);

  const value = useMemo(
    () => ({
      reducedMotion,
      texture,
      toggleReducedMotion: () => {
        const next = reducedMotion ? "full" : "reduce";
        localStorage.setItem(MOTION_KEY, next);
        setMotionPref(next);
      },
      toggleTexture: () => {
        setTexture((t) => {
          localStorage.setItem(TEXTURE_KEY, t ? "off" : "on");
          return !t;
        });
      },
    }),
    [reducedMotion, texture],
  );

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs() {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs must be used within PrefsProvider");
  return ctx;
}
