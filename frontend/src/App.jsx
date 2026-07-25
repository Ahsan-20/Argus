import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { TextureLayers } from "./components/TextureLayers.jsx";
import { AppShell } from "./components/AppShell.jsx";
import { TopBar } from "./components/TopBar.jsx";
import { RouteLoader } from "./components/RouteLoader.jsx";
import { useSession } from "./state/session.jsx";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Signup from "./pages/Signup.jsx";
import Forgot from "./pages/Forgot.jsx";
import Reset from "./pages/Reset.jsx";
import Verify from "./pages/Verify.jsx";
import Console from "./pages/Console.jsx";
import Launch from "./pages/Launch.jsx";
import Dossier from "./pages/Dossier.jsx";
import Guide from "./pages/Guide.jsx";
import Settings from "./pages/Settings.jsx";
import NotFound from "./pages/NotFound.jsx";

// Not signed in goes to the sign in page, remembering where they were headed
// so they land there instead of on a generic dashboard.
//
// `ready` matters: on a hard refresh the stored token has not been checked
// yet, and redirecting during that gap would bounce a signed-in person to the
// login screen every time they reloaded.
function RequireAccount({ children }) {
  const { signedIn, ready } = useSession();
  const location = useLocation();
  if (!ready) return null;
  if (!signedIn) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

// Someone already signed in has no use for the sign in or sign up form.
function RedirectIfSignedIn({ children }) {
  const { signedIn, ready } = useSession();
  if (!ready) return null;
  if (signedIn) return <Navigate to="/console" replace />;
  return children;
}

export default function App() {
  return (
    <>
      {/* Fixed, non-interactive atmosphere behind everything. */}
      <TextureLayers />
      {/* Covers the gap between pages while the next one's data settles. */}
      <RouteLoader />
      <div className="relative z-10">
        <Routes>
          <Route path="/" element={<Landing />} />

          <Route
            path="/login"
            element={
              <RedirectIfSignedIn>
                <Login />
              </RedirectIfSignedIn>
            }
          />
          <Route
            path="/signup"
            element={
              <RedirectIfSignedIn>
                <Signup />
              </RedirectIfSignedIn>
            }
          />
          <Route path="/forgot" element={<Forgot />} />
          {/* Reset and verify stay reachable whatever the session state: both
              are opened from a link in an email, possibly on another device,
              and bouncing those away is how a valid link looks broken. */}
          <Route path="/reset" element={<Reset />} />
          <Route path="/verify" element={<Verify />} />
          {/* The old gate. Anything still pointing at it lands somewhere real. */}
          <Route path="/enter" element={<Navigate to="/login" replace />} />

          {/* How it works is public: a first-time visitor can read it before
              signing in. The shared header adapts to the session. */}
          <Route
            path="/guide"
            element={
              <>
                <TopBar />
                <Guide />
              </>
            }
          />

          {/* Signed-in area */}
          <Route
            element={
              <RequireAccount>
                <AppShell />
              </RequireAccount>
            }
          >
            <Route path="/console" element={<Console />} />
            <Route path="/launch" element={<Launch />} />
            <Route path="/probe/:id" element={<Dossier />} />
            <Route path="/settings" element={<Settings />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </div>
    </>
  );
}
