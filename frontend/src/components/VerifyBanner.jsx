import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useSession } from "../state/session.jsx";
import { usePrefs } from "../state/prefs.jsx";
import { api } from "../lib/api.js";

// A reminder to confirm an email address, sized like a reminder.
//
// This was a full width bar wedged between the header and the page, which is
// the wrong shape for a small, later task: it pushed the whole page down, it
// was the second thing your eye landed on, and being permanently there is
// exactly what teaches people to stop seeing it.
//
// So it is now a card in the corner that says its piece and leaves. It returns
// on the next page load, which is enough nagging for something with 24 hours on
// the clock, and it stops leaving once the deadline is close.

// Long enough to read twice, short enough not to become furniture.
const DISMISS_AFTER = 9000;
// Inside this many hours it stays put, because it is no longer a reminder.
const URGENT_HOURS = 6;

export function VerifyBanner() {
  const { isVerified, signedIn, graceHoursLeft, operator } = useSession();
  const { reducedMotion } = usePrefs();
  const [hidden, setHidden] = useState(false);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const hours = Math.max(0, Math.floor(graceHoursLeft ?? 0));
  const urgent = hours <= URGENT_HOURS;
  const showing = signedIn && !isVerified && graceHoursLeft != null && !hidden;

  // Leave on its own, unless the deadline is close or there is something to
  // read. A message that vanished mid-sentence would be worse than one that
  // overstayed.
  useEffect(() => {
    if (!showing || urgent || sending || sent || error) return;
    const t = setTimeout(() => setHidden(true), DISMISS_AFTER);
    return () => clearTimeout(t);
  }, [showing, urgent, sending, sent, error]);

  // Having said "sent", there is nothing left to say.
  useEffect(() => {
    if (!sent) return;
    const t = setTimeout(() => setHidden(true), 4000);
    return () => clearTimeout(t);
  }, [sent]);

  async function resend() {
    setSending(true);
    setError("");
    try {
      await api.resendVerification();
      setSent(true);
    } catch (err) {
      setError(err.detail || "Could not send it just now");
    } finally {
      setSending(false);
    }
  }

  const left =
    hours >= 2
      ? `${hours} hours left`
      : hours === 1
        ? "1 hour left"
        : "under an hour left";

  return (
    <AnimatePresence>
      {showing && (
        <motion.div
          // Fixed, so it never moves the page. Along the bottom on a phone,
          // where the thumb already is; bottom right on a desktop.
          className="fixed inset-x-3 bottom-3 z-40 sm:inset-x-auto sm:bottom-5 sm:right-5 sm:w-[366px]"
          initial={reducedMotion ? false : { opacity: 0, y: 14, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={reducedMotion ? { opacity: 0 } : { opacity: 0, y: 10, scale: 0.98 }}
          transition={{ duration: 0.24, ease: [0.2, 0, 0, 1] }}
          role="status"
          aria-live="polite"
        >
          <div
            className="rounded-2xl border bg-panel/95 p-3.5 backdrop-blur-md"
            style={{
              borderColor: urgent ? "rgba(255,107,129,0.45)" : "var(--color-line)",
              boxShadow: "var(--card-shadow)",
            }}
          >
            <div className="flex items-start gap-3">
              <span
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px]"
                style={{
                  background: urgent
                    ? "rgba(255,107,129,0.12)"
                    : "var(--amber-fill)",
                  color: urgent ? "var(--color-red)" : "var(--color-amber)",
                }}
                aria-hidden="true"
              >
                {sent ? "✓" : "✉"}
              </span>

              <div className="min-w-0 flex-1">
                {sent ? (
                  <p className="text-[13.5px] leading-relaxed text-text2">
                    <span className="font-semibold text-text">Sent again.</span>{" "}
                    Check your inbox, and your spam folder.
                  </p>
                ) : error ? (
                  <p className="text-[13.5px] leading-relaxed text-text2">
                    <span className="font-semibold text-red">
                      Couldn't send it.
                    </span>{" "}
                    {error}
                  </p>
                ) : (
                  <p className="text-[13.5px] leading-relaxed text-text2">
                    <span className="font-semibold text-text">
                      Confirm your email
                    </span>{" "}
                    to keep your watchers running.{" "}
                    <span
                      className="whitespace-nowrap"
                      style={{
                        color: urgent
                          ? "var(--color-red)"
                          : "var(--color-label)",
                      }}
                    >
                      {left}
                    </span>
                    .
                  </p>
                )}

                {!sent && (
                  <p className="mt-0.5 truncate text-[12px] text-muted">
                    {operator}
                  </p>
                )}

                {!sent && (
                  <div className="mt-2.5 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={resend}
                      disabled={sending}
                      className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-[12.5px] font-medium text-text2 transition-colors hover:border-lineb hover:text-text disabled:opacity-60"
                    >
                      {sending && (
                        <span
                          className="inline-block h-3 w-3 shrink-0 rounded-full border-[1.5px] border-current border-t-transparent"
                          style={{
                            animation: reducedMotion
                              ? "none"
                              : "argus-spin 0.7s linear infinite",
                          }}
                          aria-hidden="true"
                        />
                      )}
                      {sending ? "Sending" : "Resend"}
                    </button>
                    <Link
                      to="/verify"
                      className="text-[12.5px] text-label hover:text-text"
                    >
                      Details
                    </Link>
                  </div>
                )}
              </div>

              {/* No dismiss once it is urgent: at that point it is not a
                  reminder any more, it is the last warning. */}
              {!urgent && (
                <button
                  type="button"
                  onClick={() => setHidden(true)}
                  aria-label="Dismiss"
                  className="-mr-1 -mt-1 shrink-0 rounded-full p-1 text-[15px] leading-none text-muted transition-colors hover:text-text"
                >
                  &times;
                </button>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
