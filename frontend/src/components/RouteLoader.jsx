import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useIsFetching } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { usePrefs } from "../state/prefs.jsx";

// The cover between pages. It goes up as the new page mounts and comes down
// when that page's data has landed.
//
// The ordering is the whole design, and getting it wrong was the original bug.
// This used to wait a moment after navigating and then decide whether to show,
// on the theory that a fast page should not be covered at all. The threshold
// was tuned twice, 180ms and then 600ms, and neither worked, because the
// question being asked was the wrong one. "Is a request still in flight" is
// not the same as "is the screen still empty". A page that renders before all
// of its data arrives, as the landing page does with its counts, is finished
// as far as the reader is concerned while a query is still running behind it.
// Deciding late meant the cover could arrive on top of a page that was already
// there, which reads as a fault.
//
// So the decision moved to the front. On navigation the cover is raised
// immediately, in a layout effect, which runs after the new page has been
// committed but before the browser paints. The reader never sees the page
// appear and then get covered, because the cover is already up in the very
// first frame the page exists.
//
// MIN_VISIBLE is what stops that being a flicker on a cached navigation.
// Having appeared, the cover stays for at least this long. It is a page
// transition, deliberately, rather than an accident of how slow the network
// happened to be.
const MIN_VISIBLE = 320;
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

  const [show, setShow] = useState(false);
  const firstRender = useRef(true);
  const shownAt = useRef(0);

  // Raise the cover as the new page mounts, but never on first paint: the app
  // has its own loading state then.
  //
  // A layout effect, not an ordinary one. Both run after React has committed
  // the new page to the DOM, but a layout effect runs before the browser
  // paints, so the state it sets is included in that same first frame. With a
  // plain effect the page would paint once uncovered and the cover would land
  // on the frame after, which is the flash this is here to avoid.
  useLayoutEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    shownAt.current = Date.now();
    setShow(true);
  }, [pathname]);

  useEffect(() => {
    if (!show) return;

    // Polling rather than reacting to loadingFresh alone, because the page
    // that was just mounted may not have registered its queries yet. For the
    // first moments after a navigation "nothing is loading" and "loading has
    // not started" are indistinguishable, and MIN_VISIBLE covers that window.
    const poll = setInterval(() => {
      if (loadingFresh === 0 && Date.now() - shownAt.current >= MIN_VISIBLE) {
        setShow(false);
      }
    }, 60);

    // A request that never resolves must not trap anyone behind the cover.
    const ceiling = setTimeout(() => setShow(false), CEILING);

    return () => {
      clearInterval(poll);
      clearTimeout(ceiling);
    };
  }, [show, loadingFresh]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="fixed inset-0 z-[80] flex items-center justify-center"
          style={{
            background: "color-mix(in srgb, var(--color-void) 92%, transparent)",
          }}
          // Appears at full strength, fades only on the way out. Fading in
          // would show the page through the cover for the length of the fade,
          // which is the glimpse this whole component exists to prevent.
          // Leaving gently is a different matter: the content is ready by
          // then, so a soft reveal is honest.
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
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
