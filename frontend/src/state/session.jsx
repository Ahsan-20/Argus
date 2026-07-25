import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  TOKEN_KEY,
  api,
  setUnauthorizedHandler,
  setVerificationHandler,
} from "../lib/api.js";

// Who is signed in.
//
// This used to be a shared passphrase everyone typed plus an email the browser
// simply asserted. Now it is one signed token issued by the server. The token
// is the only thing stored; everything about the account (address, whether it
// is confirmed, how long is left on the grace period) is asked for, because a
// client that decides its own account state can be talked out of the truth by
// anyone who can open developer tools.

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const navigate = useNavigate();
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState(null);
  // Distinguishes "no account" from "we have not asked yet", so the app can
  // hold off on redirecting anyone until it actually knows.
  const [ready, setReady] = useState(false);

  const applySession = useCallback((next) => {
    localStorage.setItem(TOKEN_KEY, next.token);
    setToken(next.token);
    setUser(next.user || null);
    setReady(true);
  }, []);

  const clear = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setReady(true);
  }, []);

  const signOut = useCallback(() => {
    clear();
    navigate("/login", { replace: true });
  }, [clear, navigate]);

  // Confirm the stored token with the server on boot. A token can be expired,
  // revoked by a rotated signing key, or belong to a deleted account, and none
  // of that is visible from the browser.
  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setReady(true);
      return;
    }
    api
      .authState()
      .then((state) => {
        if (cancelled) return;
        if (state.signed_in) {
          setUser(state.user);
        } else {
          localStorage.removeItem(TOKEN_KEY);
          setToken("");
          setUser(null);
        }
      })
      .catch(() => {
        // Backend unreachable. Keep the token rather than signing someone out
        // over a dropped connection; the next real call will sort it out.
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Re-read the account after something changes it (confirming an address).
  const refresh = useCallback(async () => {
    try {
      const fresh = await api.me();
      setUser(fresh);
      return fresh;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      localStorage.removeItem(TOKEN_KEY);
      setToken("");
      setUser(null);
      navigate("/login?expired=1", { replace: true });
    });
    setVerificationHandler(() => {
      // Signed in, but the grace period ran out. Not a login problem, so do
      // not throw away a perfectly good session over it.
      navigate("/verify?required=1", { replace: true });
    });
    return () => {
      setUnauthorizedHandler(null);
      setVerificationHandler(null);
    };
  }, [navigate]);

  const value = useMemo(
    () => ({
      token,
      user,
      ready,
      signedIn: Boolean(token),
      operator: user?.email || "",
      isVerified: Boolean(user?.is_verified),
      graceHoursLeft: user?.grace_hours_left ?? null,
      graceExpired: Boolean(user?.grace_expired),
      applySession,
      refresh,
      signOut,
    }),
    [token, user, ready, applySession, refresh, signOut],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
