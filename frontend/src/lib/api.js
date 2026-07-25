// Argus API client. One place owns the base URL, the auth headers, and the
// 401 policy, so no page has to think about them. Point VITE_API_URL at the
// backend (see .env.example); it is baked in at build time.

const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/+$/,
  "",
);

// localStorage key, shared with the session store (state/session.jsx). Read
// straight from storage here so the client has no React dependency.
//
// The old shared access code and the operator email header are gone. Identity
// now travels as a signed token the server issues and verifies, so the client
// can no longer claim to be someone it is not simply by editing a header.
export const TOKEN_KEY = "argus.token";

// The session registers a handler so a mid-session 401 (rotated code, stale
// session) is handled once, here, instead of in every page.
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

let onVerificationRequired = null;
export function setVerificationHandler(fn) {
  onVerificationRequired = fn;
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

function authHeaders() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, { method = "GET", body, headers, raw } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // Network / DNS / CORS failure: surface as a link-lost error the UI can
    // render honestly, distinct from an HTTP error status.
    throw new ApiError(0, "uplink unreachable");
  }

  // 401: the token is missing, expired or invalid, so sign out and start
  // again. 403 "verification_required" is a different thing entirely: the
  // session is fine, the account has simply run past its grace period, and
  // the person needs the verify screen rather than the login screen.
  if (res.status === 401 && onUnauthorized) onUnauthorized();
  if (res.status === 403 && onVerificationRequired) {
    let detail = "";
    try {
      detail = (await res.clone().json())?.detail || "";
    } catch {
      /* not JSON: fall through and treat it as an ordinary 403 */
    }
    if (detail === "verification_required") onVerificationRequired();
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data && data.detail) detail = data.detail;
    } catch {
      /* non-JSON error body: keep the status line */
    }
    throw new ApiError(res.status, detail);
  }

  if (raw) return res.text();
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  base: BASE,

  // --- Public / health ---
  health: () => request("/health"),
  stats: () => request("/stats"),
  pulse: () => request("/pulse", { method: "POST" }),

  // --- Accounts ---
  signup: (email, password) =>
    request("/auth/signup", { method: "POST", body: { email, password } }),
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/auth/me"),
  authState: () => request("/auth/state"),
  verifyEmail: (token) =>
    request("/auth/verify", { method: "POST", body: { token } }),
  resendVerification: () => request("/auth/resend", { method: "POST" }),
  forgotPassword: (email) =>
    request("/auth/forgot", { method: "POST", body: { email } }),
  resetPassword: (token, password) =>
    request("/auth/reset", { method: "POST", body: { token, password } }),

  // --- Fleet ---
  // No owner argument: the server reads it from the token. Passing it was
  // the bug, not the feature.
  listWatchers: () => request("/watchers"),
  listShared: () => request("/watchers?shared=true"),
  getWatcher: (id) => request(`/watchers/${id}`),
  updateWatcher: (id, body) =>
    request(`/watchers/${id}`, { method: "PATCH", body }),
  cloneWatcher: (id) => request(`/watchers/${id}/clone`, { method: "POST" }),
  runs: (id, limit = 50) => request(`/watchers/${id}/runs?limit=${limit}`),
  transmissions: (id) => request(`/watchers/${id}/transmissions`),
  clearTransmissions: (id) =>
    request(`/watchers/${id}/transmissions`, { method: "DELETE" }),

  // --- Launch (two-step) ---
  parseOrder: (sentence) =>
    request("/watchers", { method: "POST", body: { sentence } }),
  confirmWatcher: (spec) =>
    request("/watchers/confirm", { method: "POST", body: spec }),

  // --- Controls ---
  runNow: (id) => request(`/watchers/${id}/run-now`, { method: "POST" }),
  pause: (id) => request(`/watchers/${id}/pause`, { method: "POST" }),
  resume: (id) => request(`/watchers/${id}/resume`, { method: "POST" }),
  retire: (id) => request(`/watchers/${id}`, { method: "DELETE" }),

  demoTargetUrl: `${BASE}/demo/target`,
};
