import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Logo } from "./Logo.jsx";
import { Button } from "./Button.jsx";
import { useHealth } from "../hooks/useQueries.js";
import { useSession } from "../state/session.jsx";

// One header for the whole site, aware of whether you're signed in.
// Signed out: logo -> home, "How it works", and a Sign in button.
// Signed in:  logo -> dashboard, nav, a "+ New watcher" shortcut, the
//             connection dot, and an account chip that opens Settings.
// On phones the nav lives in a proper menu, not a cramped second row.

const UPLINK = {
  ok: { color: "var(--color-green)", label: "Connected" },
  degraded: { color: "var(--color-amber)", label: "Connection issues" },
  offline: { color: "var(--color-red)", label: "Offline" },
};

function NavItem({ to, children, big = false }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `rounded-full font-medium transition-colors duration-150 ${
          big ? "px-4 py-2.5 text-[15px]" : "px-3.5 py-1.5 text-[14px]"
        } ${isActive ? "bg-panel2 text-text" : "text-label hover:text-text"}`
      }
    >
      {children}
    </NavLink>
  );
}

export function TopBar() {
  const { signedIn, operator, signOut } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef(null);
  const location = useLocation();
  const health = useHealth();

  // Close both menus whenever navigation happens.
  useEffect(() => {
    setMenuOpen(false);
    setAccountOpen(false);
  }, [location.pathname]);

  // An open menu has to close on a click elsewhere and on Escape, or it is a
  // trap: on a laptop there is no back gesture to dismiss it with.
  useEffect(() => {
    if (!accountOpen) return;
    const away = (e) => {
      if (accountRef.current && !accountRef.current.contains(e.target)) {
        setAccountOpen(false);
      }
    };
    const key = (e) => e.key === "Escape" && setAccountOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", key);
    };
  }, [accountOpen]);

  const status = health.isError
    ? "offline"
    : health.data?.status === "ok"
      ? "ok"
      : health.data
        ? "degraded"
        : "offline";
  const uplink = UPLINK[status];

  const name = operator ? operator.split("@")[0] : "";
  const initial = (name[0] || "?").toUpperCase();

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-void/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center gap-4 px-4">
        {/* Logo: always goes to the home page */}
        <Link
          to="/"
          className="flex shrink-0 items-center gap-2.5"
          aria-label="Argus home"
        >
          <Logo size={27} />
          <span className="font-display text-[17px] font-bold text-text">
            Argus
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="ml-1 hidden items-center gap-1 md:flex">
          {signedIn && <NavItem to="/console">My watchers</NavItem>}
          <NavItem to="/guide">How it works</NavItem>
        </nav>

        <div className="ml-auto flex items-center gap-2.5 sm:gap-3">
          {signedIn ? (
            <>
              {/* One control at every size, and a small one: it is the
                  brightest thing on the bar, so it does not also need to be
                  the biggest. */}
              <Button
                to="/launch"
                variant="primary"
                size="xs"
                aria-label="New watcher"
              >
                + New
              </Button>

              <span
                className="hidden items-center md:flex"
                title={uplink.label}
                aria-label={`Connection: ${uplink.label}`}
              >
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: uplink.color }}
                />
              </span>

              {/* Account menu, desktop only. The chip used to be a direct
                  link to Settings, which left sign out buried at the bottom
                  of a settings page. Your name is where people look for both,
                  so it opens the two things that belong to "you" instead. */}
              <div className="relative hidden md:block" ref={accountRef}>
                <button
                  type="button"
                  onClick={() => setAccountOpen((o) => !o)}
                  aria-haspopup="menu"
                  aria-expanded={accountOpen}
                  title={`Signed in as ${operator}`}
                  className={`flex items-center gap-2 rounded-full border bg-panel py-1 pl-1 pr-2.5 transition-colors hover:border-lineb hover:bg-panel2 ${
                    accountOpen ? "border-lineb bg-panel2" : "border-line"
                  }`}
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--amber-fill)] text-[13px] font-bold text-amber">
                    {initial}
                  </span>
                  <span className="max-w-[140px] truncate text-[13px] font-medium text-text2">
                    {name}
                  </span>
                  <svg
                    width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"
                    className={`shrink-0 text-muted transition-transform ${accountOpen ? "rotate-180" : ""}`}
                  >
                    <path d="M2 4l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>

                {accountOpen && (
                  <div
                    role="menu"
                    className="absolute right-0 top-[calc(100%+8px)] w-60 overflow-hidden rounded-2xl border border-line bg-panel py-1"
                    style={{ boxShadow: "var(--card-shadow)" }}
                  >
                    <div className="border-b border-line px-3.5 py-2.5">
                      <p className="text-[11.5px] text-muted">Signed in as</p>
                      <p className="truncate text-[13px] font-medium text-text2">
                        {operator}
                      </p>
                    </div>
                    <Link
                      to="/settings"
                      role="menuitem"
                      className="block px-3.5 py-2.5 text-[13.5px] text-text2 hover:bg-raised/50 hover:text-text"
                    >
                      Settings
                    </Link>
                    {/* Set apart on purpose. It is the one item here you
                        cannot undo with the back button. */}
                    <button
                      type="button"
                      role="menuitem"
                      onClick={signOut}
                      className="block w-full border-t border-line px-3.5 py-2.5 text-left text-[13.5px] text-label hover:bg-raised/50 hover:text-red"
                    >
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                to="/login"
                className="hidden rounded-full px-3 py-1.5 text-[13.5px] font-medium text-label hover:text-text sm:inline-block"
              >
                Sign in
              </Link>
              <Button to="/signup" variant="primary" size="sm">
                Get started
              </Button>
            </div>
          )}

          {/* Mobile menu button */}
          <button
            className="flex h-10 w-10 items-center justify-center rounded-full border border-line text-text2 transition-colors hover:bg-panel2 md:hidden"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              {menuOpen ? (
                <path
                  d="M3 3l12 12M15 3L3 15"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              ) : (
                <path
                  d="M2 4.5h14M2 9h14M2 13.5h14"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu sheet */}
      {menuOpen && (
        <nav className="border-t border-line px-3 pt-2 pb-3 md:hidden">
          <div className="flex flex-col gap-1">
            {signedIn && (
              <NavItem to="/console" big>
                My watchers
              </NavItem>
            )}
            <NavItem to="/guide" big>
              How it works
            </NavItem>
            {signedIn && (
              <NavItem to="/settings" big>
                Settings
              </NavItem>
            )}
          </div>
          {signedIn ? (
            /* No "+ New watcher" here: it already sits on the bar. What the
               menu adds is the identity and the connection state, both of
               which have nowhere else to live on a phone. */
            <div className="mt-2 border-t border-line px-1 pt-3">
              {/* Sign out sits at the very bottom, past a divider, on the far
                  side from the nav items above. It is the one thing in this
                  sheet that a mis-tap cannot be undone with the back button,
                  so it does not go anywhere a thumb travels by accident. */}
              <div className="flex items-center justify-between gap-3">
                <p className="min-w-0 flex-1 truncate text-[12.5px] text-muted">
                  Signed in as {operator}
                </p>
                <button
                  type="button"
                  onClick={signOut}
                  className="shrink-0 rounded-full border border-line px-3 py-1.5 text-[12.5px] font-medium text-label active:border-red/50 active:text-red"
                >
                  Sign out
                </button>
              </div>
              <span className="mt-2 flex items-center gap-1.5">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: uplink.color }}
                />
                <span className="text-[12px] text-label">{uplink.label}</span>
              </span>
            </div>
          ) : (
            <div className="mt-2 space-y-2 border-t border-line pt-3">
              <Button to="/signup" variant="primary" className="w-full">
                Get started
              </Button>
              <Button to="/login" variant="secondary" className="w-full">
                Sign in
              </Button>
            </div>
          )}
        </nav>
      )}
    </header>
  );
}
