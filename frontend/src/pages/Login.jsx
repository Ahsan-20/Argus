import { useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { AuthShell, AuthLink, Notice } from "../components/AuthShell.jsx";
import { EmailField, PasswordField, looksLikeEmail } from "../components/PasswordField.jsx";
import { Button } from "../components/Button.jsx";
import { useSession } from "../state/session.jsx";
import { api } from "../lib/api.js";
import { useTitle } from "../hooks/useTitle.js";

export default function Login() {
  useTitle("Sign in");
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const { applySession } = useSession();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Where they were trying to get to before being sent here.
  const from = location.state?.from || "/console";
  const expired = params.get("expired");

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (!looksLikeEmail(email)) {
      setError("That does not look like an email address");
      return;
    }
    setBusy(true);
    try {
      const session = await api.login(email.trim(), password);
      applySession(session);
      navigate(from, { replace: true });
    } catch (err) {
      setError(
        err.status === 0
          ? "Could not reach Argus. It may be waking up, try again in a few seconds."
          : err.detail || "Could not sign you in",
      );
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to see what your watchers have found."
      footer={
        <>
          New here? <AuthLink to="/signup">Create an account</AuthLink>
        </>
      }
    >
      {expired && (
        <Notice tone="info">
          You were signed out because your session expired. Sign in to pick up
          where you left off.
        </Notice>
      )}
      <Notice>{error}</Notice>

      <form onSubmit={submit} className="space-y-4" noValidate>
        <EmailField value={email} onChange={setEmail} autoFocus />
        <PasswordField
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />

        <div className="flex justify-end">
          <AuthLink to="/forgot">Forgotten your password?</AuthLink>
        </div>

        <Button
          type="submit"
          variant="primary"
          className="w-full"
          disabled={busy || !email.trim() || !password}
        >
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
