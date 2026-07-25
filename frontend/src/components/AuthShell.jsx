import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Panel } from "./Panel.jsx";
import { Logo } from "./Logo.jsx";

// The frame every account screen sits in, so signing in, signing up, and
// recovering a password feel like one place rather than three.
//
// min-h-dvh rather than min-h-screen: on a phone, 100vh is the height of the
// window with the browser chrome hidden, so a centred card sits too low and
// the button can end up under the address bar. dvh follows the visible area.
export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32, ease: [0.2, 0, 0, 1] }}
        className="w-full max-w-md"
      >
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <Link to="/" aria-label="Argus home">
            <Logo size={44} />
          </Link>
          <div>
            <h1 className="font-display text-[24px] font-bold text-text">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-1 text-[14px] leading-relaxed text-label">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        <Panel>{children}</Panel>

        {footer && (
          <div className="mt-4 text-center text-[13.5px] text-muted">
            {footer}
          </div>
        )}

        {/* A way out that is not the browser's back button.
            These pages are the one place someone can arrive with no header
            and no navigation, either by following a link from an email or by
            being redirected here mid-task. The logo above does go home, but
            nobody is sure a logo is a link until they try it, and someone who
            is not ready to sign up should not have to guess. */}
        <div className="mt-6 border-t border-line pt-4 text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-[13px] text-muted transition-colors hover:text-text"
          >
            <span aria-hidden="true">&larr;</span>
            Back to home
          </Link>
        </div>
      </motion.div>
    </main>
  );
}

// Errors and confirmations look the same everywhere, and both are announced,
// because someone using a screen reader has no other way to know the form
// just rejected them.
export function Notice({ tone = "error", children }) {
  if (!children) return null;
  const map = {
    error: ["var(--color-red)", "rgba(255,107,129,0.06)", "var(--color-red)"],
    good: ["var(--color-green)", "rgba(61,220,132,0.06)", "var(--color-green)"],
    info: ["var(--color-lineb)", "var(--color-panel2)", "var(--color-text2)"],
  };
  const [border, bg, text] = map[tone] || map.error;
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      aria-live="polite"
      className="mb-4 rounded-xl border px-4 py-3 text-[13.5px] leading-relaxed"
      style={{ borderColor: border, background: bg, color: text }}
    >
      {children}
    </p>
  );
}

export function AuthLink({ to, children }) {
  return (
    <Link
      to={to}
      className="text-label underline decoration-line underline-offset-4 hover:text-text"
    >
      {children}
    </Link>
  );
}
