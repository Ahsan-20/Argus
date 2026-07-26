import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Panel } from "../components/Panel.jsx";
import { Button } from "../components/Button.jsx";
import { Field, Textarea, Toggle } from "../components/Field.jsx";
import { api } from "../lib/api.js";
import { StatusPill } from "../components/Status.jsx";
import { TrendChart } from "../components/Sparkline.jsx";
import { Countdown } from "../components/Countdown.jsx";
import { MissionLogEntry } from "../components/MissionLogEntry.jsx";
import { TransmissionView } from "../components/TransmissionView.jsx";
import { Loading, ErrorState, EmptyState } from "../components/States.jsx";
import {
  useWatcher,
  useRuns,
  useTransmissions,
  useProbeControls,
} from "../hooks/useQueries.js";
import { useToast } from "../state/toast.jsx";
import { useTitle } from "../hooks/useTitle.js";
import { WatchDial } from "../components/WatchDial.jsx";
import { Modal } from "../components/Modal.jsx";
import { GLYPH, SpecList, SpecRow } from "../components/SpecRow.jsx";
import {
  cadenceLabel,
  hostOf,
  localTime,
  probeState,
  relativeTime,
  verdictLabel,
} from "../lib/format.js";

// One glance answers "what's the situation": a headline and one quiet line.
const HERO = {
  TRIGGERED: {
    headline: "Found it",
    color: "var(--color-green)",
  },
  PAUSED: {
    headline: "Paused",
    color: "var(--color-steel)",
  },
  STANDBY: {
    headline: "Demo watcher",
    color: "var(--color-steel)",
  },
  ERROR: {
    headline: "Couldn't read the page",
    color: "var(--color-red)",
  },
};

function heroFor(state, latest) {
  if (HERO[state]) return HERO[state];
  if (!latest) {
    return { headline: "Getting ready", color: "var(--color-amber)" };
  }
  return {
    headline: latest.verdict_met === false ? "Not yet" : "Watching",
    color: "var(--color-text)",
  };
}

// Status-page style strip: one tick per check, oldest to newest.
function PulseStrip({ runs }) {
  if (runs.length < 2) return null;
  const seq = [...runs].slice(0, 40).reverse();

  // One source of truth for what a check was, so the ticks and the sentence
  // below them can never disagree.
  const KINDS = [
    { key: "found", label: "found", color: "var(--color-green)" },
    { key: "notyet", label: "not yet", color: "var(--color-steel)" },
    { key: "error", label: "couldn't read", color: "var(--color-red)" },
  ];
  const kindOf = (r) => (r.error ? "error" : r.verdict_met ? "found" : "notyet");
  const color = (r) => KINDS.find((k) => k.key === kindOf(r)).color;

  // Only outcomes that actually happened. This used to be a fixed colour key
  // listing all three every time, which after four clean checks still read
  // "Last 4 checks: found · not yet · couldn't read" and looked like a report
  // that one of them had failed.
  const tally = KINDS.map((k) => ({
    ...k,
    n: seq.filter((r) => kindOf(r) === k.key).length,
  })).filter((k) => k.n > 0);

  return (
    <div>
      {/* Ticks share out whatever width there is instead of taking a fixed
          7px each: forty of those came to roughly 400px, which overflowed a
          phone. Capped so a handful of checks do not become fat bars. */}
      <div className="flex items-end gap-[3px]" aria-hidden="true">
        {seq.map((r) => (
          <span
            key={r.id}
            title={`${verdictLabel(r)} · ${localTime(r.started_at)}`}
            className="h-5 min-w-[2px] max-w-[9px] flex-1 rounded-[3px]"
            style={{ backgroundColor: color(r), opacity: 0.85 }}
          />
        ))}
      </div>
      <p className="mt-1.5 text-[11.5px] text-muted">
        Last {seq.length} checks:{" "}
        {tally.map((k, i) => (
          <span key={k.key}>
            {i > 0 && " · "}
            <span style={{ color: k.color }}>
              {/* "4 not yet" after "Last 4 checks" says the same number twice */}
              {tally.length === 1 ? "all " : `${k.n} `}
              {k.label}
            </span>
          </span>
        ))}
      </p>
    </div>
  );
}

export default function Dossier() {
  const { id } = useParams();
  const wid = Number(id);
  const navigate = useNavigate();
  const toast = useToast();

  const watcherQ = useWatcher(wid);
  const runsQ = useRuns(wid);
  const txQ = useTransmissions(wid);
  const controls = useProbeControls(wid);
  const qc = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(null);
  const [sharePending, setSharePending] = useState(false);
  const [clearingAlerts, setClearingAlerts] = useState(false);
  // The tab carries this watcher's own name, so several open at once stay
  // tellable apart. Called before the early returns: hooks cannot be skipped.
  useTitle(watcherQ.data?.callsign || "Watcher");

  if (watcherQ.isLoading) {
    // Normally unseen: the route cover is over this for the whole fetch. It
    // matters when that cover times out on a request that never finishes,
    // where the alternative is a blank page that looks broken. Holds the
    // height the watcher will occupy so nothing jumps when the data lands.
    return (
      <main className="mx-auto min-h-[60vh] max-w-[980px] px-4 py-10">
        <Panel>
          <Loading label="Opening this watcher…" />
        </Panel>
      </main>
    );
  }
  if (watcherQ.isError) {
    return (
      <main className="mx-auto max-w-[980px] px-4 py-10">
        <ErrorState error={watcherQ.error} onRetry={watcherQ.refetch} />
      </main>
    );
  }

  const w = watcherQ.data;
  const runs = runsQ.data || [];
  const latest = runs[0];
  const state = probeState(w, latest);
  const paused = w.status === "paused";
  const triggered = w.status === "triggered";
  const hero = heroFor(state, latest);
  const adaptive =
    w.base_cadence_minutes && w.base_cadence_minutes !== w.cadence_minutes;

  const trackedPoints = runs
    .filter((r) => r.extracted)
    .map((r) => ({ value: r.extracted, at: r.started_at }))
    .reverse();

  const finds = runs.filter((r) => r.verdict_met).length;
  const unreadable = runs.filter((r) => r.error).length;
  const alerts = txQ.data || [];

  async function checkNow() {
    try {
      const run = await controls.runNow.mutateAsync();
      const sure =
        run?.confidence != null && !run.error ? ` (${run.confidence}% sure)` : "";
      let message = `Checked just now: ${verdictLabel(run)}${sure}`;
      let ttl = 3600;
      if (triggered && run?.verdict_met && !run?.error) {
        message +=
          ". No new alert was sent: this watcher already found it and is standing down. Press Resume watching to arm alerts again.";
        ttl = 8000;
      }
      toast.push(message, {
        tone: run?.error ? "error" : run?.verdict_met ? "success" : "info",
        ttl,
      });
    } catch (err) {
      toast.push(err.detail || "That check didn't go through, try again", {
        tone: "error",
      });
    }
  }

  async function control(kind, message) {
    try {
      await controls[kind].mutateAsync();
      toast.push(message, { tone: "success" });
    } catch (err) {
      toast.push(err.detail || "That didn't work, try again", { tone: "error" });
    }
  }

  async function remove() {
    try {
      await controls.retire.mutateAsync();
      toast.push(`${w.callsign} deleted`, { tone: "info" });
      navigate("/console");
    } catch (err) {
      toast.push(err.detail || "Couldn't delete it, try again", { tone: "error" });
    }
  }

  function startEdit() {
    setForm({
      callsign: w.callsign,
      url: w.url,
      condition: w.condition,
      track: w.track || "",
      cadence_minutes: w.cadence_minutes,
      email: w.email,
      repeating: Boolean(w.repeating),
    });
    setEditing(true);
  }

  async function saveEdit() {
    setSaving(true);
    try {
      await api.updateWatcher(wid, {
        callsign: form.callsign,
        url: form.url,
        condition: form.condition,
        track: form.track,
        cadence_minutes: Number(form.cadence_minutes) || w.cadence_minutes,
        email: form.email,
        repeating: Boolean(form.repeating),
      });
      qc.invalidateQueries({ queryKey: ["watcher", wid] });
      qc.invalidateQueries({ queryKey: ["fleet"] });
      qc.invalidateQueries({ queryKey: ["runs", wid] });
      toast.push("Watcher updated", { tone: "success" });
      setEditing(false);
    } catch (err) {
      toast.push(err.detail || "Couldn't save. Check the fields", { tone: "error" });
    } finally {
      setSaving(false);
    }
  }

  async function toggleShare(next) {
    if (sharePending) return;
    setSharePending(true);
    try {
      await api.updateWatcher(wid, { is_shared: next });
      await qc.invalidateQueries({ queryKey: ["watcher", wid] });
      qc.invalidateQueries({ queryKey: ["shared"] });
      toast.push(next ? "Now shared with everyone" : "No longer shared", {
        tone: "success",
      });
    } catch (err) {
      toast.push(err.detail || "Couldn't change sharing", { tone: "error" });
    } finally {
      setSharePending(false);
    }
  }

  async function clearAlerts() {
    if (clearingAlerts) return;
    setClearingAlerts(true);
    try {
      await api.clearTransmissions(wid);
      await qc.invalidateQueries({ queryKey: ["transmissions", wid] });
      toast.push("All alerts cleared", { tone: "info" });
    } catch (err) {
      toast.push(err.detail || "Couldn't clear alerts", { tone: "error" });
    } finally {
      setClearingAlerts(false);
    }
  }

  // The one quiet line under the headline.
  function statusLine() {
    if (state === "ERROR" && latest?.error) {
      return (
        <>
          <span className="text-red">{latest.error}</span>. Next try{" "}
          <Countdown target={w.next_run_at} />.
        </>
      );
    }
    if (triggered)
      return "The alert is below. Resume watching to catch the next change.";
    if (paused) return "Paused. Argus isn't checking right now.";
    if (state === "STANDBY") return "Runs only during demos.";
    if (!latest)
      return "First check is running. The result appears in a moment.";
    return (
      <>
        Checked {relativeTime(latest.started_at)}
        {latest.confidence != null ? (
          <span title="How sure Argus was of this verdict, by its own reckoning">
            {" "}
            · {latest.confidence}% sure
          </span>
        ) : null}{" "}
        · next check <Countdown target={w.next_run_at} />
      </>
    );
  }

  return (
    <main className="mx-auto max-w-[980px] px-4 py-6 sm:py-8">
      <button
        onClick={() => navigate("/console")}
        className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-line bg-panel px-3.5 py-1.5 text-[13px] font-medium text-label transition-colors hover:border-lineb hover:bg-panel2 hover:text-text"
      >
        <span aria-hidden="true">←</span> My watchers
      </button>

      {/* Title */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="font-display text-[26px] font-bold text-text sm:text-[30px]">
          {w.callsign}
        </h1>
        <StatusPill state={state} />
        {w.is_shared && (
          <span
            className="rounded-full border border-amber/40 px-2 py-0.5 text-[11px] text-amber"
            title="Shared. Others can see and copy this watcher"
          >
            sharing
          </span>
        )}
      </div>
      <p className="mt-1.5 line-clamp-2 max-w-[62ch] text-[14.5px] leading-relaxed text-text2">
        Watching <span className="font-semibold text-text">{hostOf(w.url)}</span>
        : {w.condition}
      </p>

      {/* The situation: what it is doing, said once and shown once */}
      <div
        className="mt-5 overflow-hidden rounded-2xl border border-line bg-panel"
        style={{ boxShadow: "var(--card-shadow)" }}
      >
        <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:gap-7 sm:p-6">
          {/* the dial: a real clock for the wait, and the state at a glance */}
          <div className="mx-auto shrink-0 sm:mx-0">
            <WatchDial
              state={state}
              nextRunAt={w.next_run_at}
              cadenceMinutes={w.cadence_minutes}
              checking={controls.runNow.isPending}
            />
          </div>

          <div className="min-w-0 flex-1">
            <p
              className="font-display text-[26px] font-bold leading-tight sm:text-[28px]"
              style={{ color: hero.color }}
            >
              {controls.runNow.isPending ? "Checking now" : hero.headline}
            </p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">
              {controls.runNow.isPending
                ? "Reading the page and weighing it against what you asked for."
                : statusLine()}
            </p>

            {latest?.evidence && !latest.error && (
              <p className="mt-3 line-clamp-2 max-w-[58ch] border-l-2 border-amber pl-3 text-[13px] italic leading-relaxed text-label">
                “{latest.evidence}”
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button
                variant={paused || triggered ? "primary" : "secondary"}
                size="sm"
                disabled={controls.resume.isPending || controls.pause.isPending}
                onClick={() =>
                  paused || triggered
                    ? control("resume", "Back to watching")
                    : control("pause", "Paused")
                }
              >
                {paused || triggered
                  ? controls.resume.isPending
                    ? "Resuming…"
                    : "Resume watching"
                  : controls.pause.isPending
                    ? "Pausing…"
                    : "Pause"}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={checkNow}
                disabled={controls.runNow.isPending}
              >
                {controls.runNow.isPending ? "Checking…" : "Check now"}
              </Button>
              <Button variant="ghost" size="sm" href={w.url}>
                Open the page ↗
              </Button>
            </div>
          </div>
        </div>

        {runs.length > 1 && (
          <div className="border-t border-line px-5 py-4 sm:px-6">
            <PulseStrip runs={runs} />
          </div>
        )}
      </div>

      {/* Alerts: the payoff, right after the situation */}
      {alerts.length > 0 && (
        <Panel
          title="Alerts sent"
          className="mt-5"
          bodyClass="p-0 pt-0"
          actions={
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAlerts}
              disabled={clearingAlerts}
            >
              {clearingAlerts ? "Clearing…" : "Clear all"}
            </Button>
          }
        >
          <div className="max-h-[560px] overflow-y-auto p-5">
            <div className="max-w-[720px] space-y-4">
              {alerts.map((ev) => {
                let payload = null;
                try {
                  payload = JSON.parse(ev.payload);
                } catch {
                  payload = null;
                }
                return (
                  <TransmissionView
                    key={ev.id}
                    payload={payload}
                    stamp={ev.created_at}
                  />
                );
              })}
            </div>
          </div>
        </Panel>
      )}

      {/* Tracked value: only once there is something to show */}
      {w.track && trackedPoints.length > 0 && (
        <Panel title={`Tracking: ${w.track}`} className="mt-5">
          {trackedPoints.length >= 2 ? (
            <TrendChart points={trackedPoints} />
          ) : (
            <p className="text-[14px] text-text2">
              First value:{" "}
              <span className="font-semibold text-amber">
                {trackedPoints[0].value}
              </span>{" "}
              <span className="text-[12.5px] text-muted">
                · the chart appears after a few more checks
              </span>
            </p>
          )}
        </Panel>
      )}

      {/* Editing happens in a floating window: one task, full attention, and
          the page behind keeps its shape instead of reflowing around a form. */}
      <Modal
        open={Boolean(editing && form)}
        onClose={saving ? undefined : () => setEditing(false)}
        title={`Edit ${w.callsign}`}
        subtitle="Change anything here. Nothing is saved until you press save."
        footer={
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-[12.5px] leading-relaxed text-muted">
              Changing the page or the condition clears its memory and checks
              again.
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditing(false)}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={saveEdit} disabled={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </div>
        }
      >
        {form && (
          <div className="space-y-4">
            <Field
              label="Name it"
              value={form.callsign}
              onChange={(v) => setForm((f) => ({ ...f, callsign: v }))}
            />
            <Field
              label="Page to watch"
              value={form.url}
              onChange={(v) => setForm((f) => ({ ...f, url: v }))}
            />
            <Textarea
              label="What Argus looks for"
              rows={2}
              value={form.condition}
              onChange={(v) => setForm((f) => ({ ...f, condition: v }))}
            />
            <Field
              label="Also keep track of (optional)"
              value={form.track}
              onChange={(v) => setForm((f) => ({ ...f, track: v }))}
              placeholder="e.g. the current price"
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Check every (minutes)"
                type="number"
                min={15}
                max={1440}
                value={form.cadence_minutes}
                onChange={(v) => setForm((f) => ({ ...f, cadence_minutes: v }))}
              />
              <Field
                label="Alerts go to"
                type="email"
                value={form.email}
                onChange={(v) => setForm((f) => ({ ...f, email: v }))}
              />
            </div>

            <div className="flex items-start justify-between gap-4 rounded-xl border border-line bg-panel2 px-4 py-3">
              <div>
                <p className="text-[14px] font-medium text-text2">
                  Keep telling me every time
                </p>
                <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted">
                  On: it reports every move, like a price or a rate. Off: it
                  alerts once, then stands down.
                </p>
              </div>
              <Toggle
                checked={Boolean(form.repeating)}
                onChange={(v) => setForm((f) => ({ ...f, repeating: v }))}
              />
            </div>
          </div>
        )}
      </Modal>

      {/* History + setup */}
      {/* minmax(0,1fr) rather than 1fr: a bare 1fr track still floors at the
          content's min-width, so a column holding nowrap text can refuse to
          shrink and push the page sideways. */}
      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel
          title="Check history"
          bodyClass="p-0 pt-0"
          actions={
            runs.length ? (
              <span className="text-[12.5px] text-muted">
                {runs.length} {runs.length === 1 ? "check" : "checks"} · {finds}{" "}
                found ·{" "}
                {unreadable ? `${unreadable} couldn't read` : "no trouble"}
              </span>
            ) : null
          }
        >
          {runsQ.isLoading ? (
            <div className="p-5">
              <Loading label="Loading history…" />
            </div>
          ) : runs.length ? (
            // Eight rows, then it scrolls. Chosen so the card finishes at
            // roughly the height of the setup card beside it instead of
            // towering over it.
            <div className="max-h-[368px] overflow-y-auto">
              {runs.map((r) => (
                <MissionLogEntry key={r.id} run={r} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No checks yet"
              message="History shows up here after the first check."
            />
          )}
        </Panel>

        <Panel
          title="How it's set up"
          actions={
            !w.is_demo ? (
              <Button variant="ghost" size="sm" onClick={startEdit}>
                Edit
              </Button>
            ) : null
          }
        >
          {(
            <>
              <SpecList>
                <SpecRow
                  icon={GLYPH.clock}
                  label="Checks every"
                  value={cadenceLabel(w.cadence_minutes)}
                  highlight={Boolean(adaptive)}
                  note={
                    adaptive
                      ? `You asked for ${cadenceLabel(w.base_cadence_minutes)}. Argus adjusted it to match how often this page really changes.`
                      : null
                  }
                />
                {w.track && (
                  <SpecRow
                    icon={GLYPH.track}
                    label="Also tracking"
                    value={w.track}
                  />
                )}
                <SpecRow
                  icon={GLYPH.bell}
                  label="Alerts"
                  value={w.repeating ? "Every time it moves" : "Once, then stands down"}
                  highlight={Boolean(w.repeating)}
                />
                <SpecRow
                  icon={GLYPH.mail}
                  label="Alerts go to"
                  value={w.email}
                />
                <SpecRow
                  icon={GLYPH.flag}
                  label="Watching since"
                  value={localTime(w.created_at)}
                />
              </SpecList>
              {!w.is_demo && (
                <div className="mt-3 flex items-center justify-between gap-4 border-t border-line pt-3.5">
                  <div>
                    <p className="text-[13.5px] font-medium text-text2">
                      Share with everyone
                    </p>
                    <p className="text-[12px] text-muted">
                      Others can see and copy this watcher.
                    </p>
                  </div>
                  <Toggle
                    checked={Boolean(w.is_shared)}
                    onChange={toggleShare}
                    disabled={sharePending}
                  />
                </div>
              )}
            </>
          )}
        </Panel>
      </div>

      {/* Delete: quiet single row, not a whole card */}
      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
        <p className="text-[13px] text-muted">
          Deleting removes this watcher and its history. This can't be undone.
        </p>
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <Button
              variant="dangerSolid"
              size="sm"
              onClick={remove}
              disabled={controls.retire.isPending}
            >
              {controls.retire.isPending ? "Deleting…" : "Yes, delete it"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
              Keep it
            </Button>
          </div>
        ) : (
          <Button variant="danger" size="sm" onClick={() => setConfirmDelete(true)}>
            Delete…
          </Button>
        )}
      </div>
    </main>
  );
}
