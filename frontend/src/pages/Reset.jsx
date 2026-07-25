import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AuthShell, AuthLink, Notice } from "../components/AuthShell.jsx";
import { MIN_PASSWORD, PasswordField } from "../components/PasswordField.jsx";
import { Button } from "../components/Button.jsx";
import { useSession } from "../state/session.jsx";
import { api } from "../lib/api.js";
import { useTitle } from "../hooks/useTitle.js";

export default function Reset() {
  useTitle("Choose a new password");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { applySession } = useSession();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      // Signed in on success, because someone who just proved they own the
      // inbox should not immediately be asked to type the password they set
      // four seconds ago.
      const session = await api.resetPassword(token, password);
      applySession(session);
      navigate("/console", { replace: true });
    } catch (err) {
      setError(err.detail || "Could not reset your password");
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <AuthShell
        title="That link is incomplete"
        subtitle="The reset link was missing its code."
        footer={<AuthLink to="/login">Back to sign in</AuthLink>}
      >
        <Notice>
          Open the link straight from the email, or ask for a new one.
        </Notice>
        <Button variant="primary" className="w-full" to="/forgot">
          Send me a new link
        </Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Pick something long. You will be signed in straight after."
      footer={<AuthLink to="/login">Back to sign in</AuthLink>}
    >
      <Notice>{error}</Notice>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <PasswordField
          label="New password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          showStrength
          autoFocus
          hint={`At least ${MIN_PASSWORD} characters.`}
        />
        <Button
          type="submit"
          variant="primary"
          className="w-full"
          disabled={busy || password.length < MIN_PASSWORD}
        >
          {busy ? "Saving…" : "Save and sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
