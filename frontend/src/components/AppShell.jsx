import { useEffect, useRef } from "react";
import { Outlet } from "react-router-dom";
import { TopBar } from "./TopBar.jsx";
import { VerifyBanner } from "./VerifyBanner.jsx";
import { api } from "../lib/api.js";

const PULSE_INTERVAL = 60_000;

// The signed-in shell: top bar + routed content. Also pings the presence
// beacon so the free backend stays warm while someone is actually looking.
export function AppShell() {
  const lastPulse = useRef(0);

  useEffect(() => {
    const ping = () => {
      if (document.visibilityState !== "visible") return;
      const now = Date.now();
      if (now - lastPulse.current < PULSE_INTERVAL) return;
      lastPulse.current = now;
      api.pulse().catch(() => {});
    };
    ping();
    document.addEventListener("visibilitychange", ping);
    return () => document.removeEventListener("visibilitychange", ping);
  }, []);

  return (
    <div className="min-h-screen">
      <TopBar />
      <VerifyBanner />
      <Outlet />
    </div>
  );
}
