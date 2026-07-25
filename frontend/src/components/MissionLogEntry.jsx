import { useState } from "react";
import { motion } from "framer-motion";
import { localTime, relativeTime, verdictLabel } from "../lib/format.js";

// One check, told as a sentence. Expands for the full story. A failed check is
// reported plainly: the watcher saying "I couldn't read the page" is still the
// watcher doing its job.
export function MissionLogEntry({ run, callsign, animate = false }) {
  const [open, setOpen] = useState(false);
  const isError = Boolean(run.error);
  const met = run.verdict_met === true;

  const dotColor = isError
    ? "var(--color-red)"
    : met
      ? "var(--color-green)"
      : "var(--color-steel)";

  return (
    <motion.div
      initial={animate ? { opacity: 0, y: 4 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.2, 0, 0, 1] }}
      className="border-b border-line last:border-b-0"
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-raised/40"
      >
        <span
          className="inline-block h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: dotColor }}
        />
        {callsign && (
          <span className="text-[13px] font-semibold text-text2">{callsign}</span>
        )}
        <span className="text-[13.5px] font-medium" style={{ color: dotColor }}>
          {verdictLabel(run)}
        </span>
        {run.confidence != null && !isError && (
          <span
            className="text-[12.5px] text-muted"
            title="How sure Argus was of this verdict, by its own reckoning"
          >
            {run.confidence}% sure
          </span>
        )}
        {run.extracted && (
          <span className="rounded-full bg-panel2 px-2 py-0.5 text-[12px] text-amber">
            {run.extracted}
          </span>
        )}
        <span
          className="ml-auto text-[12.5px] text-muted"
          title={localTime(run.started_at)}
        >
          {relativeTime(run.started_at)}
        </span>
        <span className="text-[13px] text-label">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className="space-y-3 px-4 pb-4 pl-9">
          {isError ? (
            <p className="text-[13.5px] leading-relaxed text-red">{run.error}</p>
          ) : (
            <>
              {run.reasoning && (
                <p className="text-[13.5px] leading-relaxed text-text2">
                  {run.reasoning}
                </p>
              )}
              {run.evidence && (
                <div>
                  <span className="label mb-1 block">Seen on the page</span>
                  <p className="rounded-lg border-l-2 border-amber bg-panel2 px-3 py-2 text-[13px] italic leading-relaxed text-text2">
                    “{run.evidence}”
                  </p>
                </div>
              )}
            </>
          )}
          <p className="data text-muted">
            {localTime(run.started_at)}
            {run.provider ? ` · checked by ${run.provider}` : ""}
          </p>
        </div>
      )}
    </motion.div>
  );
}
