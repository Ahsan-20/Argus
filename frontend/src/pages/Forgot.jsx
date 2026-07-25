import { useState } from "react";
import { AuthShell, AuthLink, Notice } from "../components/AuthShell.jsx";
import { EmailField, looksLikeEmail } from "../components/PasswordField.jsx";
import { Button } from "../components/Button.jsx";
import { api } from "../lib/api.js";
import { useTitle } from "../hooks/useTitle.js";

export default function Forgot() {
  useTitle("Reset your password");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (!looksLikeEmail(email)) {
      setError("That does not look like an email address");
      return;
    }
    setBusy(true);
    try {
      await api.forgotPassword(email.trim());
      // Deliberately the same screen whether or not that address has an
      // account. Saying "no account with that email" would turn this page
      // into a way of asking who is registered here, one address at a time.
      setSent(true);
    } catch (err) {
      setError(
        err.status === 0
          ? "Could not reach Argus. It may be waking up, try again in a few seconds."
          : err.detail || "Something went wrong. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <AuthShell
        title="Check your email"
        subtitle="If that address has an account, a reset link is on its way."
        footer={<AuthLink to="/login">Back to sign in</AuthLink>}
      >
        <Notice tone="good">
          The link works for one hour and can only be used once. If it does not
          arrive within a minute or two, check your spam folder.
        </Notice>
        <Button
          variant="secondary"
          className="w-full"
          onClick={() => setSent(false)}
        >
          Use a different address
        </Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Forgotten your password?"
      subtitle="Give us your address and we will send you a link to set a new one."
      footer={<AuthLink to="/login">Back to sign in</AuthLink>}
    >
      <Notice>{error}</Notice>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <EmailField value={email} onChange={setEmail} autoFocus />
        <Button
          type="submit"
          variant="primary"
          className="w-full"
          disabled={busy || !email.trim()}
        >
          {busy ? "Sending…" : "Send me a reset link"}
        </Button>
      </form>
    </AuthShell>
  );
}
