import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";

// A centred floating window for one focused task.
//
// Escape closes it, so does clicking the dark backdrop, and the page behind is
// locked so the background cannot scroll away underneath. Passing no onClose
// (while saving, say) makes it modal in the strict sense: nothing dismisses it
// until the work finishes.
export function Modal({ open, onClose, title, subtitle, children, footer, maxWidth = 580 }) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Move focus into the dialog so the keyboard follows the eye.
    const t = setTimeout(() => {
      const first = panelRef.current?.querySelector(
        "input, textarea, button, [tabindex]:not([tabindex='-1'])",
      );
      first?.focus();
    }, 60);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
      clearTimeout(t);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:items-center sm:p-6">
          <motion.div
            className="fixed inset-0 bg-black/65 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={() => onClose?.()}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className="relative w-full rounded-2xl border border-lineb bg-panel"
            style={{ maxWidth, boxShadow: "0 24px 70px rgba(0,0,0,0.55)" }}
            initial={{ opacity: 0, y: 14, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
          >
            <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
              <div>
                <h2 className="font-display text-[17px] font-bold text-text">
                  {title}
                </h2>
                {subtitle && (
                  <p className="mt-0.5 text-[13px] leading-relaxed text-muted">
                    {subtitle}
                  </p>
                )}
              </div>
              {onClose && (
                <button
                  onClick={onClose}
                  aria-label="Close"
                  className="-mr-1 -mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-label transition-colors hover:bg-panel2 hover:text-text"
                >
                  <svg width="15" height="15" viewBox="0 0 15 15" aria-hidden="true">
                    <path
                      d="M3 3l9 9M12 3l-9 9"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              )}
            </header>

            <div className="max-h-[64vh] overflow-y-auto px-5 py-4">{children}</div>

            {footer && (
              <div className="border-t border-line px-5 py-4">{footer}</div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
