import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useIsFetching } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { usePrefs } from "../state/prefs.jsx";

// The pause between pages, shown only when there is genuinely a pause.
//
// No artificial minimum: a navigation whose data is already cached shows
// nothing at all, because inventing a delay to justify an animation would be
// lying to the user about how fast their app is.
//
// GRACE exists for correctness, not for show. A freshly mounted page has not
// registered its queries yet, so for the first fraction of a second "nothing
// is loading" and "loading has not started" look identical. Waiting that out
// before deciding also means fast navigations slip past unnoticed, which is
// the behaviour we want anyway.
//
// SETTLE only applies once the overlay is actually on screen: having appeared,
// vanishing in the same breath reads as a glitch rather than as speed.
const GRACE = 180;
const SETTLE = 300;
const CEILING = 10_000;

export function RouteLoader() {
  const { pathname } = useLocation();
  // Only queries that have nothing to show yet. Counting every fetch meant a
  // background refresh of already-cached data lit the overlay up, which is
  // why returning to a page you had already visited flashed it AFTER the page
  // was on screen: the content was there, and a routine refetch was running
  // behind it. A page with data is not loading, whatever the network is doing.
  const loadingFresh = useIsFetching({
    predicate: (q) => q.state.data === undefined,
  });
  const { reducedMotion } = usePrefs();

  const [watching, setWatching] = useState(false); // a navigation is in flight
  const [show, setShow] = useState(false);
  const firstRender = useRef(true);
  const navAt = useRef(0);
  const shownAt = useRef(0);

  // Begin watching on navigation, but never on first paint: the app has its
  // own loading state then.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    navAt.current = Date.now();
    setWatching(true);
  }, [pathname]);

  useEffect(() => {
    if (!watching) return;

    const poll = setInterval(() => {
      const sinceNav = Date.now() - navAt.current;

      if (!show) {
        if (sinceNav < GRACE) return; // too early to tell
        if (loadingFresh > 0) {
          shownAt.current = Date.now();
          setShow(true); // genuinely slow, worth covering
        } else {
          setWatching(false); // arrived instantly, say nothing
        }
        return;
      }

      if (loadingFresh === 0 && Date.now() - shownAt.current >= SETTLE) {
        setShow(false);
        setWatching(false);
      }
    }, 60);

    // A request that never resolves must not trap anyone behind the overlay.
    const ceiling = setTimeout(() => {
      setShow(false);
      setWatching(false);
    }, CEILING);

    return () => {
      clearInterval(poll);
      clearTimeout(ceiling);
    };
  }, [watching, show, loadingFresh]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 z-[80] flex items-center justify-center"
          style={{
            background: "color-mix(in srgb, var(--color-void) 92%, transparent)",
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          aria-live="polite"
          aria-busy="true"
        >
          <div className="flex flex-col items-center gap-4">
            <svg width="72" height="72" viewBox="0 0 72 72" role="img" aria-label="Loading">
              <defs>
                <linearGradient id="routeSweep" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="var(--color-amber)" stopOpacity="0" />
                  <stop offset="100%" stopColor="var(--color-amber)" stopOpacity="1" />
                </linearGradient>
              </defs>

              <circle cx="36" cy="36" r="26" fill="none" stroke="var(--color-line)" strokeWidth="2" />

              {!reducedMotion && (
                <g className="orbit-ring" style={{ animationDuration: "1.1s" }}>
                  <circle
                    cx="36" cy="36" r="26"
                    fill="none" stroke="url(#routeSweep)" strokeWidth="2.5"
                    strokeLinecap="round" strokeDasharray="42 122"
                  />
                </g>
              )}

              <ellipse
                cx="36" cy="36" rx="11" ry="7"
                fill="none" stroke="var(--color-amber)" strokeWidth="1.8"
              />
              <circle cx="36" cy="36" r="3.4" fill="var(--color-amber)" />
            </svg>
            <span className="text-[13px] font-medium text-label">Loading…</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
