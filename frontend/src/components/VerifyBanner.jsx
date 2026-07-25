import { useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../state/session.jsx";
import { api } from "../lib/api.js";

// A quiet reminder for an account that has not confirmed its address yet.
//
// It gets more insistent as the deadline approaches rather than shouting from
// the start, because a banner that looks like an emergency on day one is a
// banner people learn to ignore by the time it matters. Dismissible for the
// same reason: nagging someone who is mid-task just teaches them to stop
// reading the thing you need them to read.
export function VerifyBanner() {
  const { isVerified, signedIn, graceHoursLeft, operator } = useSession();
  const [hidden, setHidden] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const hours = Math.max(0, Math.floor(graceHoursLeft ?? 0));
  const urgent = hours <= 6;

  // Dismissable early, not late. Hiding it on day one is a fair choice and
  // keeps the reminder from becoming wallpaper. Hiding it with two hours to
  // go means the watchers stop and the only warning was one someone waved
  // away yesterday, so past the urgent mark it stays put.
  if (!signedIn || isVerified || graceHoursLeft == null) return null;
  if (hidden && !urgent) return null;
  const left =
    hours >= 2
      ? `${hours} hours left`
      : hours === 1
        ? "1 hour left"
        : "less than an hour left";

  async function resend() {
    setError("");
    try {
      await api.resendVerification();
      setSent(true);
    } catch (err) {
      setError(err.detail || "Could not send it just now");
    }
  }

  return (
    <div
      className="border-b"
      style={{
        borderColor: urgent ? "rgba(255,107,129,0.4)" : "var(--color-line)",
        background: urgent ? "rgba(255,107,129,0.07)" : "var(--amber-fill)",
      }}
    >
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2.5">
        <p className="min-w-0 flex-1 text-[13px] leading-relaxed text-text2">
          <span className="font-semibold text-text">
            Confirm your email{urgent ? " now" : ""}.
          </span>{" "}
          {sent ? (
            <>Sent again to {operator}. Check your inbox.</>
          ) : error ? (
            <span className="text-red">{error}</span>
          ) : (
            <>
              We sent a link to {operator}.{" "}
              <span className={urgent ? "text-red" : "text-label"}>{left}</span>{" "}
              before your watchers pause.
            </>
          )}
        </p>
        <div className="flex shrink-0 items-center gap-3">
          {!sent && (
            <button
              type="button"
              onClick={resend}
              className="text-[12.5px] font-semibold text-amber hover:underline"
            >
              Resend
            </button>
          )}
          <Link
            to="/verify"
            className="text-[12.5px] font-semibold text-label hover:text-text"
          >
            Details
          </Link>
          {!urgent && (
            <button
              type="button"
              onClick={() => setHidden(true)}
              aria-label="Hide this reminder"
              className="text-[15px] leading-none text-muted hover:text-text"
            >
              &times;
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
