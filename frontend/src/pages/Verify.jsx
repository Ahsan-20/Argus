import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AuthShell, AuthLink, Notice } from "../components/AuthShell.jsx";
import { Button } from "../components/Button.jsx";
import { useSession } from "../state/session.jsx";
import { api } from "../lib/api.js";
import { useTitle } from "../hooks/useTitle.js";

// Two jobs on one page, because they are two ends of the same thread:
//
//  /verify?token=...   the link from the email. Confirms and lets them in.
//  /verify?required=1  the wall, once the grace period has run out.
//
// Keeping them together means the link always lands somewhere that makes
// sense, even for someone who is already confirmed or already signed in.
export default function Verify() {
  useTitle("Confirm your email");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { applySession, signedIn, operator, isVerified, signOut } = useSession();

  const token = params.get("token") || "";
  const required = params.get("required");

  const [phase, setPhase] = useState(token ? "checking" : "idle");
  const [error, setError] = useState("");
  const [resent, setResent] = useState("");
  const ran = useRef(false);

  // React runs effects twice in development. Without this the token is spent
  // on the first pass and the second reports it as already used, which looks
  // like a broken link to anyone testing.
  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;
    api
      .verifyEmail(token)
      .then((session) => {
        applySession(session);
        setPhase("done");
        setTimeout(() => navigate("/console", { replace: true }), 1400);
      })
      .catch((err) => {
        // Never blame the link for a network failure. Telling someone their
        // link expired when the service is simply asleep sends them off asking
        // for new links that will fail the same way.
        setError(
          err.status === 0
            ? "Could not reach Argus to check this link. It may be waking up, which takes up to a minute. Try again shortly, the link is still good."
            : err.detail || "That link is not valid or has expired",
        );
        setPhase("failed");
      });
  }, [token, applySession, navigate]);

  async function resend() {
    setResent("");
    setError("");
    try {
      await api.resendVerification();
      setResent("Sent. Check your inbox in a moment.");
    } catch (err) {
      setError(
        err.status === 0
          ? "Could not reach Argus just now. It may be waking up, try again in a moment."
          : err.detail || "Could not send it just now",
      );
    }
  }

  const failed = phase === "failed";
  // A dead link on an account that is already confirmed is not a problem,
  // it is just a stale email. Worth saying so rather than staying silent.
  const failedButVerified = failed && isVerified;

  if (phase === "checking") {
    return (
      <AuthShell title="Confirming your email" subtitle="One moment.">
        <Notice tone="info">Checking your link…</Notice>
      </AuthShell>
    );
  }

  // Confirmed wins over everything except the spinner. An account that is
  // already sorted should never be shown a scary "this link has expired",
  // which is exactly what someone gets for clicking a two week old email a
  // second time. The state of the account is the truth; the link is just how
  // they got here.
  if (phase === "done" || isVerified) {
    return (
      <AuthShell
        title="You are all set"
        subtitle="Your email is confirmed."
        footer={<AuthLink to="/console">Go to your watchers</AuthLink>}
      >
        <Notice tone="good">
          {failedButVerified
            ? "That link has already been used, but there is nothing to do: this address is confirmed."
            : "Confirmed. Argus will keep watching and emailing you as normal."}
        </Notice>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={required ? "Confirm your email to carry on" : "Confirm your email"}
      subtitle={
        required
          ? "The 24 hours are up. One click and everything picks back up where it was."
          : "We sent you a link. Open it and you are done."
      }
      footer={
        signedIn ? (
          <button
            type="button"
            onClick={signOut}
            className="text-label underline decoration-line underline-offset-4 hover:text-text"
          >
            Sign out
          </button>
        ) : (
          <AuthLink to="/login">Back to sign in</AuthLink>
        )
      }
    >
      {failed && <Notice>{error}</Notice>}
      {!failed && error && <Notice>{error}</Notice>}
      {resent && <Notice tone="good">{resent}</Notice>}

      {required && !failed && !resent && (
        <Notice tone="info">
          Nothing has been lost. Your watchers and their history are exactly as
          you left them, and they start again the moment you confirm.
        </Notice>
      )}

      {signedIn ? (
        <>
          <p className="text-[14px] leading-relaxed text-text2">
            The link went to{" "}
            <span className="font-semibold text-text">{operator}</span>. If it
            never arrived, check your spam folder, then send another.
          </p>
          <Button variant="primary" className="mt-4 w-full" onClick={resend}>
            Send the link again
          </Button>
        </>
      ) : (
        <>
          <p className="text-[14px] leading-relaxed text-text2">
            Sign in first and we can send you a fresh confirmation link.
          </p>
          <Button variant="primary" className="mt-4 w-full" to="/login">
            Sign in
          </Button>
        </>
      )}
    </AuthShell>
  );
}
