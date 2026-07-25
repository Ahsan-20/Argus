import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Panel } from "../components/Panel.jsx";
import { Button } from "../components/Button.jsx";
import { OrbitMap } from "../components/OrbitMap.jsx";
import { StatusPill } from "../components/Status.jsx";
import { Countdown } from "../components/Countdown.jsx";
import { TelemetryTicker } from "../components/TelemetryTicker.jsx";
import { Loading, ErrorState, EmptyState } from "../components/States.jsx";
import {
  useFleet,
  useSharedFleet,
  useStats,
  useProbeControls,
} from "../hooks/useQueries.js";
import { useSession } from "../state/session.jsx";
import { useToast } from "../state/toast.jsx";
import { api } from "../lib/api.js";
import {
  STATE_META,
  cadenceLabel,
  compactValue,
  hostOf,
  probeState,
  relativeTime,
  truncate,
  verdictLabel,
} from "../lib/format.js";
import { useTitle } from "../hooks/useTitle.js";

// Little glyphs for the stat cards, drawn inline so they inherit the theme.
const GLYPHS = {
  orbit: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="5.2" stroke="var(--color-amber)" strokeWidth="1.4" />
      <circle cx="14.2" cy="4.4" r="1.9" fill="var(--color-amber)" />
    </svg>
  ),
  eye: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <ellipse cx="9" cy="9" rx="7" ry="4.4" stroke="var(--color-amber)" strokeWidth="1.4" />
      <circle cx="9" cy="9" r="2" fill="var(--color-amber)" />
    </svg>
  ),
  bell: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <path
        d="M4.5 12.5v-4a4.5 4.5 0 0 1 9 0v4l1.4 1.8H3.1l1.4-1.8Z"
        stroke="var(--color-green)"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M7.6 16a1.6 1.6 0 0 0 2.8 0" stroke="var(--color-green)" strokeWidth="1.4" />
    </svg>
  ),
  pulse: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <path
        d="M1.5 9.5h3.4L7 4.5l3.6 9 1.9-4h4"
        stroke="var(--color-amber)"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
};

function Stat({ glyph, value, label }) {
  return (
    <div
      className="flex items-center gap-3 rounded-2xl border border-line bg-panel px-4 py-3.5"
      style={{ boxShadow: "var(--card-shadow)" }}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--amber-fill)]">
        {glyph}
      </span>
      <div className="min-w-0">
        <p className="tnum font-display text-[20px] font-bold leading-none text-text">
          {value ?? "-"}
        </p>
        <p className="mt-1 truncate text-[12px] text-label">{label}</p>
      </div>
    </div>
  );
}

// One watcher as a readable card. Actions are always visible — never hidden
// behind hover, because phones have no hover.
function WatcherCard({ w }) {
  const navigate = useNavigate();
  const toast = useToast();
  const controls = useProbeControls(w.id);
  const state = probeState(w);
  const paused = w.status === "paused";
  const last = w.last_run;
  // A countdown only means something while it is actually counting down.
  const showNext = !paused && state !== "STANDBY" && state !== "TRIGGERED";

  async function act(kind, message) {
    try {
      await controls[kind].mutateAsync();
      toast.push(message, { tone: "success" });
    } catch (err) {
      toast.push(err.detail || "That didn't work, try again", { tone: "error" });
    }
  }

  // Check now reports its result, and explains when no alert will be sent.
  async function checkNow() {
    try {
      const run = await controls.runNow.mutateAsync();
      const sure =
        run?.confidence != null && !run.error ? ` (${run.confidence}% sure)` : "";
      let message = `${w.callsign}: ${verdictLabel(run)}${sure}`;
      let ttl = 3600;
      if (state === "TRIGGERED" && run?.verdict_met && !run?.error) {
        message +=
          ". No new alert: it already found this and is standing down. Resume watching to arm alerts again.";
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

  const verdictColor = !last
    ? "var(--color-muted)"
    : last.error
      ? "var(--color-red)"
      : last.verdict_met
        ? "var(--color-green)"
        : "var(--color-text2)";

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-line bg-panel transition-colors hover:border-lineb"
      style={{ boxShadow: "var(--card-shadow)" }}
    >
      {/* A stripe in the state's colour, so a list of these is scanned down
          the left edge instead of read card by card. */}
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ background: STATE_META[state].color, opacity: 0.9 }}
      />

      <div
        className="cursor-pointer py-3.5 pl-5 pr-4 sm:py-4 sm:pl-6 sm:pr-5"
        onClick={() => navigate(`/probe/${w.id}`)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && navigate(`/probe/${w.id}`)}
        aria-label={`Open ${w.callsign}`}
      >
        {/* Who it is, and how it is set up.
            The name is a plain block, not a flex item: a flex item defaults to
            min-width:auto and so refuses to shrink below its own text, which
            defeats truncate and lets a long name push the card off screen. */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="truncate font-display text-[16.5px] font-semibold text-text">
              {w.callsign}
            </h3>
            {/* The cadence and the chips are context, not answers. They earn
                their place on a wide card and only crowd a phone, where the
                same facts are one tap away on the watcher's own page. */}
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="min-w-0 truncate text-[12.5px] text-muted">
                {hostOf(w.url)}
                <span className="hidden sm:inline">
                  {" "}
                  · every {cadenceLabel(w.cadence_minutes)}
                </span>
              </span>
              {w.is_shared && (
                <span
                  className="hidden shrink-0 rounded-full border border-amber/40 px-1.5 py-0.5 text-[10.5px] text-amber sm:inline"
                  title="You're sharing this watcher. Others can see and copy it"
                >
                  sharing
                </span>
              )}
              {w.repeating && (
                <span
                  className="hidden shrink-0 rounded-full border border-line px-1.5 py-0.5 text-[10.5px] text-muted sm:inline"
                  title="Alerts every time this moves, rather than once"
                >
                  repeating
                </span>
              )}
            </div>
          </div>
          <StatusPill state={state} className="shrink-0" />
        </div>

        {/* What it watches on the left, what it found on the right. These used
            to stack, which on a desktop card left the entire right half empty
            and made a list of watchers a tall column of mostly nothing. Side
            by side, the answers line up in a column the eye can run down. */}
        <div className="mt-2.5 sm:flex sm:items-end sm:justify-between sm:gap-6">
          {/* What it looks for. One line on a phone, where a mid-word cut
              across two lines reads worse than an honest ellipsis; two on a
              desktop, where there is room to actually say it. */}
          <p
            className="truncate text-[14px] text-text2 sm:line-clamp-2 sm:min-w-0 sm:flex-1 sm:whitespace-normal"
            title={w.condition}
          >
            {w.condition}
          </p>

          {/* The answer, then the clock. These were one line of four items at
              the same weight, which ran together into "Not yet 41 min ago next
              any moment now" and made two different times look like one. The
              verdict is what people came for, so it leads; when it last looked
              and when it looks again are a quiet caption underneath, and each
              now says which one it is. */}
          <div className="mt-3 sm:mt-0 sm:max-w-[46%] sm:shrink-0 sm:text-right">
            <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 sm:justify-end">
              <span
                className="text-[14.5px] font-semibold"
                style={{ color: verdictColor }}
              >
                {last ? verdictLabel(last) : "First check running"}
              </span>
              {last?.extracted && (
                <span
                  className="rounded-full bg-panel2 px-2 py-0.5 text-[12px] font-medium text-amber"
                  title={last.extracted}
                >
                  {compactValue(last.extracted)}
                </span>
              )}
            </div>

            {(last || showNext) && (
              <p className="mt-1 text-[12px] text-muted">
                {last && `checked ${relativeTime(last.started_at)}`}
                {last && showNext && " · "}
                {showNext && (
                  <>
                    next <Countdown target={w.next_run_at} quiet />
                  </>
                )}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* flex-wrap matters: a triggered card reads "Check now / Resume
          watching / Details", which is wider than a phone. Without it the row
          overflows instead of stacking. */}
      <div className="flex flex-wrap items-center gap-1 border-t border-line py-2 pl-5 pr-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={checkNow}
          disabled={controls.runNow.isPending}
        >
          {controls.runNow.isPending ? "Checking…" : "Check now"}
        </Button>
        {state === "TRIGGERED" ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={controls.resume.isPending}
            onClick={() => act("resume", `${w.callsign} is watching again`)}
          >
            {controls.resume.isPending ? "Resuming…" : "Resume watching"}
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            disabled={controls.pause.isPending || controls.resume.isPending}
            onClick={() =>
              act(
                paused ? "resume" : "pause",
                paused ? `${w.callsign} resumed` : `${w.callsign} paused`,
              )
            }
          >
            {paused
              ? controls.resume.isPending
                ? "Resuming…"
                : "Resume"
              : controls.pause.isPending
                ? "Pausing…"
                : "Pause"}
          </Button>
        )}
        {/* Desktop only. The whole card is already a link to this page, so on
            a phone this button is a second control doing the first one's job
            while taking a third of the row. */}
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto hidden sm:inline-flex"
          onClick={() => navigate(`/probe/${w.id}`)}
        >
          Details →
        </Button>
      </div>
    </div>
  );
}

// A watcher someone else is sharing: shown inert, with one action — copy it
// into your own fleet. Your copy gets its own history and your alert email.
function SharedCard({ w, operator }) {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [cloning, setCloning] = useState(false);
  const mine = operator && w.owner_email === operator;

  async function useIt() {
    setCloning(true);
    try {
      const copy = await api.cloneWatcher(w.id);
      qc.invalidateQueries({ queryKey: ["fleet"] });
      toast.push(`${copy.callsign} added to your watchers`, { tone: "success" });
      navigate(`/probe/${copy.id}`);
    } catch (err) {
      toast.push(err.detail || "Couldn't copy it, try again", { tone: "error" });
      setCloning(false);
    }
  }

  return (
    <div
      className="rounded-2xl border border-line bg-panel p-5"
      style={{ boxShadow: "var(--card-shadow)" }}
    >
      {/* Same shape as a watcher card: the name is a block so it can actually
          truncate, and the owner's email is a long unbroken string that has to
          be allowed to shorten. */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-display text-[16px] font-semibold text-text">
            {w.callsign}
          </h3>
          <p className="mt-1 truncate text-[12px] text-muted">
            shared by {mine ? "you" : w.owner_email || "the facility"}
          </p>
        </div>
        <StatusPill state="PAUSED" className="shrink-0" />
      </div>
      <p className="mt-2.5 text-[14.5px] leading-relaxed text-text2">
        Watching{" "}
        <span className="font-semibold text-text">{hostOf(w.url)}</span>:{" "}
        {truncate(w.condition, 90)}
      </p>
      {w.track && (
        <p className="mt-1.5 text-[13px] text-muted">Also tracks: {w.track}</p>
      )}
      <div className="mt-3.5 flex items-center gap-2">
        {mine ? (
          <Button variant="ghost" size="sm" onClick={() => navigate(`/probe/${w.id}`)}>
            This is yours. Open it →
          </Button>
        ) : (
          <>
            <Button variant="primary" size="sm" onClick={useIt} disabled={cloning}>
              {cloning ? "Adding…" : "Use this watcher"}
            </Button>
            <span className="text-[12px] text-muted">
              Makes your own copy. Alerts go to you.
            </span>
          </>
        )}
      </div>
    </div>
  );
}

export default function Console() {
  useTitle("My watchers");
  const navigate = useNavigate();
  const { operator } = useSession();
  const toast = useToast();
  const stats = useStats();

  const [view, setView] = useState("mine"); // mine | found | shared
  const [query, setQuery] = useState("");
  const fleetQ = useFleet(operator);
  const sharedQ = useSharedFleet(view === "shared");
  const fleet = fleetQ.data || [];
  const shared = sharedQ.data || [];

  const firstName = operator ? operator.split("@")[0] : "there";

  // Watchers this operator owns count toward their personal limit. The shared
  // facility examples (no owner) are visible to all and do not count.
  const perUserLimit = stats.data?.limits?.per_user;
  const mineCount = useMemo(
    () => fleet.filter((w) => operator && w.owner_email === operator).length,
    [fleet, operator],
  );
  const atLimit = perUserLimit != null && mineCount >= perUserLimit;

  // Watchers that found their thing live in their own tab, not the main list.
  const active = useMemo(
    () => fleet.filter((w) => w.status !== "triggered"),
    [fleet],
  );
  const found = useMemo(
    () => fleet.filter((w) => w.status === "triggered"),
    [fleet],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return active;
    return active.filter(
      (w) =>
        w.callsign.toLowerCase().includes(q) ||
        hostOf(w.url).toLowerCase().includes(q) ||
        (w.condition || "").toLowerCase().includes(q),
    );
  }, [active, query]);

  // Recent activity, clearable per account (the timestamp lives in this
  // browser, keyed by the signed-in email).
  const clearKey = `argus.activity.cleared.${operator || "anon"}`;
  const [clearedAt, setClearedAt] = useState(
    () => Number(localStorage.getItem(clearKey) || 0),
  );
  function clearActivity() {
    const now = Date.now();
    localStorage.setItem(clearKey, String(now));
    setClearedAt(now);
  }

  const recent = useMemo(() => {
    return fleet
      .filter((w) => w.last_run)
      .map((w) => ({ ...w.last_run, callsign: w.callsign, watcherId: w.id }))
      .filter((r) => new Date(r.started_at).getTime() > clearedAt)
      .sort((a, b) => new Date(b.started_at) - new Date(a.started_at))
      .slice(0, 15);
  }, [fleet, clearedAt]);

  const empty = !fleetQ.isLoading && active.length === 0;

  return (
    <>
      <TelemetryTicker stats={stats.data} fleetCount={fleet.length} />

      <main className="mx-auto max-w-[1200px] px-4 py-6 sm:py-8">
        {/* Greeting + the one primary action */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="font-display text-[26px] font-bold text-text sm:text-[30px]">
              Hi, {firstName}
            </h1>
            <p className="mt-1 text-[14.5px] text-label sm:text-[15px]">
              {/* The pleasantry is desktop only. On a phone the line has one
                  job: say how many slots are left. */}
              <span className="hidden sm:inline">
                Here's what Argus is keeping an eye on for you.
              </span>
              {perUserLimit != null && (
                <>
                  {" "}
                  <span className={atLimit ? "text-amber" : "text-muted"}>
                    You're using {mineCount} of your {perUserLimit} watchers.
                  </span>
                </>
              )}
            </p>
          </div>
          <Button
            to="/launch"
            variant="primary"
            className="w-full sm:w-auto"
            title={
              atLimit
                ? `You have ${mineCount} of ${perUserLimit} watchers. Delete one to free a slot.`
                : undefined
            }
          >
            + Watch something new
          </Button>
        </div>

        {atLimit && (
          <div className="mt-4 rounded-xl border border-amber/40 bg-[var(--amber-fill)] px-4 py-3">
            <p className="text-[13.5px] leading-relaxed text-text2">
              <span className="font-semibold text-text">
                You've used all {perUserLimit} of your watcher slots.
              </span>{" "}
              Delete one you no longer need, and the slot frees up right away.
              Watchers in the Found tab still count, so clearing those out is
              usually the easiest win.
            </p>
          </div>
        )}

        {/* The sky at a glance. Desktop only: on a phone these four cards
            repeat what the summary line above already says, and cost two rows
            of scroll before anyone reaches their own watchers. */}
        {stats.data && (
          <div className="mt-6 hidden grid-cols-2 gap-3 sm:grid lg:grid-cols-4">
            {/* Yours, not the whole site's. These sit directly under a line
                saying "you are using 3 of your 5 watchers", so site-wide
                totals here read as personal ones: it reported 6 finds and 20
                checks to someone who had 0 finds and 6 checks, because the
                rest belonged to the shared watchers. Only the last card is
                about everyone, and it now says so. */}
            <Stat
              glyph={GLYPHS.eye}
              value={stats.data.mine?.active_watchers ?? 0}
              label="Your watchers on duty"
            />
            <Stat
              glyph={GLYPHS.pulse}
              value={(stats.data.mine?.total_runs ?? 0).toLocaleString()}
              label="Checks made for you"
            />
            <Stat
              glyph={GLYPHS.bell}
              value={stats.data.mine?.positive_verdicts ?? 0}
              label="Finds so far"
            />
            <Stat
              glyph={GLYPHS.orbit}
              value={stats.data.total_watchers}
              label="Watchers across Argus"
            />
          </div>
        )}

        {/* Mine / shared tabs */}
        <div className="mt-7 flex w-fit items-center gap-1 rounded-full border border-line bg-panel p-1">
          {[
            ["mine", "My watchers"],
            ["found", `Found${found.length ? ` (${found.length})` : ""}`],
            ["shared", "Shared"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`rounded-full px-4 py-1.5 text-[13.5px] font-medium transition-colors ${
                view === key ? "bg-amber text-void" : "text-label hover:text-text"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* min-w-0 on both columns is load bearing. A grid item defaults to
            min-width:auto, so it sizes to its widest content: the watcher
            cards clip their condition with white-space:nowrap, whose
            max-content width is the whole sentence. Without this the column
            grew to fit that sentence and pushed the page off screen. */}
        <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          {/* Left column */}
          <div className="min-w-0 space-y-4">
            {view === "mine" ? (
              <>
                {/* Search, when there's something to search */}
                {active.length > 3 && (
                  <input
                    type="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search your watchers by name, site, or what they look for…"
                    className="w-full rounded-xl border border-line bg-panel2 px-4 py-2.5 text-[14px] text-text placeholder:text-muted focus:border-amber"
                    aria-label="Search your watchers"
                  />
                )}

                {fleetQ.isLoading ? (
                  <Panel>
                    <Loading label="Loading your watchers…" />
                  </Panel>
                ) : fleetQ.isError ? (
                  <ErrorState error={fleetQ.error} onRetry={fleetQ.refetch} />
                ) : empty ? (
                  <Panel>
                    <EmptyState
                      title="Nothing being watched yet"
                      message="Describe what to keep an eye on, or copy one of the ready made watchers from the Shared tab."
                      action={
                        <div className="flex flex-wrap items-center justify-center gap-2">
                          <Button to="/launch" variant="primary">
                            Set up your first watcher
                          </Button>
                          <Button variant="secondary" onClick={() => setView("shared")}>
                            Browse shared
                          </Button>
                        </div>
                      }
                    />
                  </Panel>
                ) : filtered.length === 0 ? (
                  <Panel>
                    <EmptyState
                      title="No matches"
                      message={`Nothing matches "${query}".`}
                    />
                  </Panel>
                ) : (
                  // Roughly five cards tall, then its own scrollbar.
                  <div className="max-h-[840px] space-y-4 overflow-y-auto pr-1">
                    {filtered.map((w) => (
                      <WatcherCard key={w.id} w={w} />
                    ))}
                  </div>
                )}
              </>
            ) : view === "found" ? (
              <>
                <p className="text-[13.5px] leading-relaxed text-muted">
                  Watchers that found what they were looking for. Press Resume
                  watching to send one back on duty for the next change.
                </p>
                {found.length === 0 ? (
                  <Panel>
                    <EmptyState
                      title="Nothing found yet"
                      message="When a watcher finds its thing, it moves here so you can review it."
                    />
                  </Panel>
                ) : (
                  <div className="max-h-[840px] space-y-4 overflow-y-auto pr-1">
                    {found.map((w) => (
                      <WatcherCard key={w.id} w={w} />
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="text-[13.5px] leading-relaxed text-muted">
                  Watchers other people are sharing. Copy one and it becomes
                  yours: your alerts, your history, fully separate.
                </p>
                {sharedQ.isLoading ? (
                  <Panel>
                    <Loading label="Loading shared watchers…" />
                  </Panel>
                ) : (shared || []).length === 0 ? (
                  <Panel>
                    <EmptyState
                      title="Nothing shared yet"
                      message="When someone shares a watcher, it shows up here for everyone."
                    />
                  </Panel>
                ) : (
                  <div className="max-h-[840px] space-y-4 overflow-y-auto pr-1">
                    {shared.map((w) => (
                      <SharedCard key={w.id} w={w} operator={operator} />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Side column. On a phone these sit under the watchers, and the
              order flips: what happened recently is worth more than a picture
              of the sky, so the orbit goes last. */}
          <div className="flex min-w-0 flex-col gap-4">
            {/* Desktop only. On a phone it was a 300px decorative block
                stranded below everything that matters, which is the worst of
                both: it costs the scroll and nobody scrolls to it. The dial
                on each watcher's own page carries the same life. */}
            <Panel
              title="Your sky right now"
              className="hidden lg:order-1 lg:block"
            >
              <p className="-mt-1 mb-2 text-[13px] leading-relaxed text-muted">
                Every dot is a watcher circling its page. Faster orbit, more
                frequent checks. Tap one to open it.
              </p>
              <div className="flex items-center justify-center">
                <OrbitMap
                  watchers={fleet}
                  onSelect={(id) => navigate(`/probe/${id}`)}
                  callsign={firstName}
                  compact
                />
              </div>
            </Panel>

            <Panel
              className="order-1 lg:order-2"
              title="Recent activity"
              bodyClass="p-0 pt-0"
              actions={
                recent.length ? (
                  <Button variant="ghost" size="sm" onClick={clearActivity}>
                    Clear
                  </Button>
                ) : null
              }
            >
              {recent.length ? (
                // Compact rows built for this narrow column: one line of
                // status, one optional line of what was seen. Roughly three
                // visible, the rest scroll. Tap a row to open the watcher.
                <div className="max-h-[186px] overflow-y-auto" aria-live="polite">
                  {recent.map((r) => (
                    <button
                      key={`${r.callsign}-${r.id}`}
                      onClick={() => navigate(`/probe/${r.watcherId}`)}
                      className="flex w-full items-baseline gap-2 border-b border-line px-5 py-2.5 text-left last:border-b-0 hover:bg-raised/40"
                    >
                        <span
                          className="relative top-[-1px] inline-block h-2 w-2 shrink-0 rounded-full"
                          style={{
                            backgroundColor: r.error
                              ? "var(--color-red)"
                              : r.verdict_met
                                ? "var(--color-green)"
                                : "var(--color-steel)",
                          }}
                        />
                        <span className="truncate text-[13px] font-semibold text-text">
                          {r.callsign}
                        </span>
                        <span
                          className="truncate text-[12.5px] font-medium"
                          style={{
                            color: r.error
                              ? "var(--color-red)"
                              : r.verdict_met
                                ? "var(--color-green)"
                                : "var(--color-text2)",
                          }}
                        >
                          {verdictLabel(r)}
                        </span>
                        <span className="ml-auto shrink-0 text-[11.5px] text-muted">
                          {relativeTime(r.started_at)}
                        </span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="px-5 pb-4">
                  <p className="text-[13px] leading-relaxed text-muted">
                    All caught up. New checks appear here as they happen.
                  </p>
                </div>
              )}
            </Panel>
          </div>
        </div>
      </main>
    </>
  );
}
