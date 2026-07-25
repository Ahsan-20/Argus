import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthShell, AuthLink, Notice } from "../components/AuthShell.jsx";
import {
  EmailField,
  MIN_PASSWORD,
  PasswordField,
  looksLikeEmail,
} from "../components/PasswordField.jsx";
import { Button } from "../components/Button.jsx";
import { useSession } from "../state/session.jsx";
import { api } from "../lib/api.js";
import { useTitle } from "../hooks/useTitle.js";

export default function Signup() {
  useTitle("Create an account");
  const navigate = useNavigate();
  const { applySession } = useSession();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [emailError, setEmailError] = useState("");
  const [busy, setBusy] = useState(false);

  const ready = looksLikeEmail(email) && password.length >= MIN_PASSWORD;

  async function submit(e) {
    e.preventDefault();
    setError("");
    setEmailError("");
    if (!looksLikeEmail(email)) {
      setEmailError("That does not look like an email address");
      return;
    }
    setBusy(true);
    try {
      // Signed in straight away. Making someone go and find a confirmation
      // email before they have seen anything is how you lose the people who
      // were only half curious.
      const session = await api.signup(email.trim(), password);
      applySession(session);
      navigate("/console?welcome=1", { replace: true });
    } catch (err) {
      setError(
        err.status === 0
          ? "Could not reach Argus. It may be waking up, try again in a few seconds."
          : err.detail || "Could not create your account",
      );
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Your email is both your sign in and where alerts arrive."
      footer={
        <>
          Already have an account? <AuthLink to="/login">Sign in</AuthLink>
        </>
      }
    >
      <Notice>{error}</Notice>

      <form onSubmit={submit} className="space-y-4" noValidate>
        <EmailField
          value={email}
          onChange={(v) => {
            setEmail(v);
            if (emailError) setEmailError("");
          }}
          error={emailError}
          autoFocus
          hint="Alerts go here, so use one you actually read."
        />
        <PasswordField
          label="Choose a password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          showStrength
          hint={`At least ${MIN_PASSWORD} characters. Longer beats complicated.`}
        />

        <Button
          type="submit"
          variant="primary"
          className="w-full"
          disabled={busy || !ready}
        >
          {busy ? "Creating your account…" : "Create account"}
        </Button>

        <p className="text-center text-[12.5px] leading-relaxed text-muted">
          You can start straight away. We will email you a link to confirm the
          address, and Argus keeps working for 24 hours while you get to it.
        </p>
      </form>
    </AuthShell>
  );
}
