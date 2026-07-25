import { motion } from "framer-motion";
import { Button } from "../components/Button.jsx";
import { useTitle } from "../hooks/useTitle.js";

export default function NotFound() {
  useTitle("Page not found");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <svg width="120" height="120" viewBox="0 0 120 120" aria-hidden="true">
        <circle cx="60" cy="60" r="46" fill="none" stroke="var(--color-line)" strokeWidth="1.5" />
        <motion.circle
          cx="60"
          cy="14"
          r="4"
          fill="var(--color-amber)"
          animate={{ rotate: 360 }}
          transition={{ duration: 40, repeat: Infinity, ease: "linear" }}
          style={{ transformOrigin: "60px 60px", transformBox: "view-box" }}
        />
      </svg>
      <h1 className="mt-8 font-display text-[26px] font-bold text-text">
        This page drifted off
      </h1>
      <p className="mt-2 text-[14.5px] text-muted">
        There's nothing at this address. Let's get you back.
      </p>
      <Button to="/console" variant="primary" className="mt-6">
        Back to my watchers
      </Button>
    </main>
  );
}
