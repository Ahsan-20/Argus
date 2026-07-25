import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Panel } from "../components/Panel.jsx";
import { Field, Textarea, Toggle } from "../components/Field.jsx";
import { Button } from "../components/Button.jsx";
import { WatchDial } from "../components/WatchDial.jsx";
import { api, ApiError } from "../lib/api.js";
import { useSession } from "../state/session.jsx";
import { usePrefs } from "../state/prefs.jsx";
import { useToast } from "../state/toast.jsx";
import { useFleet, useSharedFleet, useStats } from "../hooks/useQueries.js";
import { useTitle } from "../hooks/useTitle.js";
import { hostOf, truncate } from "../lib/format.js";

// Short labels, full sentences. The old version put whole sentences on the
// chips, which made each one a full-width row instead of something tappable.
const EXAMPLES = [
  ["A software release", "Tell me when Python 4 shows up on python.org/downloads"],
  ["An appointment slot", "Watch this page for an appointment slot before September"],
  ["Back in stock", "Let me know when this item is back in stock, and track the price"],
  ["Exam results", "Tell me when exam results are posted on this page"],
  ["A price drop", "Tell me every time the price drops by 500 or more on this page"],
];

// What Argus is doing while the Commissioner reads the order. Real stages, in
// the order they actually happen, so the wait explains itself.
const THINKING = [
  "Reading your sentence",
  "Finding the page you mean",
  "Working out exactly what to look for",
  "Choosing how often to check",
];

const STEPS = ["Describe it", "Check the plan", "Watching"];

function Progress({ step }) {
  return (
    <>
      {/* On a phone three unlabelled circles say nothing. One honest line
          says the same thing in less space. */}
      <p className="mb-5 text-[13px] font-medium text-muted sm:hidden">
        Step {step + 1} of {STEPS.length}
        <span className="text-text2"> · {STEPS[step]}</span>
      </p>
      <ol className="mb-7 hidden items-center gap-2 sm:flex">
      {STEPS.map((label, i) => {
        const state = i < step ? "done" : i === step ? "now" : "todo";
        return (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11.5px] font-bold transition-colors"
              style={{
                background:
                  state === "todo" ? "var(--color-panel2)" : "var(--color-amber)",
                color: state === "todo" ? "var(--color-muted)" : "var(--color-void)",
              }}
            >
              {state === "done" ? "✓" : i + 1}
            </span>
            <span
              className="hidden text-[12.5px] font-medium sm:inline"
              style={{
                color:
                  state === "now" ? "var(--color-text)" : "var(--color-muted)",
              }}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <span
                className="h-px flex-1 transition-colors"
                style={{
                  background:
                    i < step ? "var(--color-amber)" : "var(--color-line)",
                }}
              />
            )}
          </li>
        );
      })}
      </ol>
    </>
  );
}

// A tick that lights up once the sentence contains what it needs. Live
// feedback while typing beats an error after pressing the button.
function Hint({ ok, children }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[12.5px] transition-colors"
      style={{ color: ok ? "var(--color-green)" : "var(--color-muted)" }}
    >
      <span
        className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold transition-colors"
        style={{
          background: ok ? "var(--color-green)" : "transparent",
          border: ok ? "none" : "1px solid var(--color-lineb)",
          color: "var(--color-void)",
        }}
      >
        {ok ? "✓" : ""}
      </span>
      {children}
    </span>
  );
}

// The column beside the form: what a good request looks like, and what other
// people are actually watching. Real watchers, not invented examples.
// Mounted only where it is shown, so the shared-watchers request is never
// made for a phone that will not display the result.
function Sidebar({ onPick }) {
  const shared = useSharedFleet(true);
  const examples = (shared.data || []).slice(0, 4);

  return (
    <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
      <Panel title="What makes it work">
        <ul className="space-y-3">
          {[
            ["Name the page", "Paste the address, or enough of it to find."],
            ["Say the moment", "\"when tickets go on sale\", not \"if anything changes\"."],
            ["Add a value to follow", "\"and track the price\" gives you a chart over time."],
          ].map(([title, body]) => (
            <li key={title} className="flex gap-2.5">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
              <div>
                <p className="text-[13.5px] font-medium text-text2">{title}</p>
                <p className="text-[12.5px] leading-relaxed text-muted">{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </Panel>

      {examples.length > 0 && (
        <Panel title="Already being watched">
          <p className="-mt-1 mb-3 text-[12.5px] leading-relaxed text-muted">
            Real watchers people are sharing. Tap one to start from it.
          </p>
          <div className="space-y-2">
            {examples.map((w) => (
              <button
                key={w.id}
                onClick={() =>
                  onPick(`Watch ${w.url} and tell me: ${w.condition}`)
                }
                className="w-full rounded-xl border border-line bg-panel2 px-3 py-2.5 text-left transition-colors hover:border-amber/50"
              >
                <p className="truncate text-[13px] font-medium text-text2">
                  {w.callsign}
                </p>
                <p className="mt-0.5 truncate text-[12px] text-muted">
                  {hostOf(w.url)} · {truncate(w.condition, 46)}
                </p>
              </button>
            ))}
          </div>
        </Panel>
      )}
    </aside>
  );
}

export default function Launch() {
  useTitle("New watcher");
  const navigate = useNavigate();
  const { operator } = useSession();
  const { reducedMotion } = usePrefs();
  const toast = useToast();

  // Know the operator's standing before they write anything, so the limit is
  // never a surprise at the final step.
  const stats = useStats();
  const fleetQ = useFleet(operator);
  const perUserLimit = stats.data?.limits?.per_user;
  const mineCount = (fleetQ.data || []).filter(
    (w) => operator && w.owner_email === operator,
  ).length;
  const atLimit = perUserLimit != null && mineCount >= perUserLimit;

  const [sentence, setSentence] = useState("");
  const [phase, setPhase] = useState("command"); // command | parsing | brief | launching | done
  const [spec, setSpec] = useState(null);
  const [launched, setLaunched] = useState(null);
  const [rejection, setRejection] = useState("");
  const [fleetFull, setFleetFull] = useState("");
  const [thought, setThought] = useState(0);

  // Walk the thinking lines while the Commissioner works.
  useEffect(() => {
    if (phase !== "parsing") return setThought(0);
    const t = setInterval(
      () => setThought((n) => Math.min(n + 1, THINKING.length - 1)),
      1300,
    );
    return () => clearInterval(t);
  }, [phase]);

  const hasAddress = /(https?:\/\/\S+|\b[\w-]+\.(com|org|net|io|pk|gov|edu|co)\b)/i.test(
    sentence,
  );
  const hasWish = sentence.trim().split(/\s+/).length >= 5;
  const stepIndex = phase === "command" || phase === "parsing" ? 0 : phase === "done" ? 2 : 1;

  async function parse(e) {
    e?.preventDefault();
    if (!sentence.trim()) return;
    setPhase("parsing");
    setRejection("");
    try {
      const parsed = await api.parseOrder(sentence.trim());
      setSpec({ ...parsed, email: parsed.email || operator || "" });
      setPhase("brief");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setRejection(
          err.detail ||
            "Argus couldn't turn that into a watcher. Try adding the page's address.",
        );
      } else {
        setRejection(
          err.detail || "Couldn't reach Argus just now. Give it a moment and try again.",
        );
      }
      setPhase("command");
    }
  }

  async function launch() {
    setPhase("launching");
    setFleetFull("");
    try {
      const watcher = await api.confirmWatcher(spec);
      setLaunched(watcher);
      setPhase("done");
      // Let the moment land before moving on: the watcher has just taken up
      // its post and it is worth a beat to show it.
      setTimeout(() => navigate(`/probe/${watcher.id}`), reducedMotion ? 400 : 1900);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setFleetFull(
          err.detail ||
            "No free slots right now. Delete a watcher you no longer need, then try again.",
        );
      } else {
        toast.push(err.detail || "Couldn't start the watcher, try again", {
          tone: "error",
        });
      }
      setPhase("brief");
    }
  }

  const setField = (k) => (v) => setSpec((s) => ({ ...s, [k]: v }));

  // The final screen owns the full width; the working steps sit in a column
  // with the helper beside them, so the page is never mostly empty.
  const showSidebar = phase === "command" || phase === "parsing";

  return (
    <main
      className={`mx-auto px-4 py-8 sm:py-10 ${
        showSidebar ? "max-w-[1060px]" : "max-w-[720px]"
      }`}
    >
      <div
        className={
          showSidebar ? "grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]" : ""
        }
      >
        <div className="min-w-0">
      {phase !== "done" && <Progress step={stepIndex} />}

      <AnimatePresence mode="wait">
        {/* ---------------------------------------------------- step 1 */}
        {(phase === "command" || phase === "parsing") && (
          <motion.div
            key="command"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: [0.2, 0, 0, 1] }}
          >
            <h1 className="font-display text-[26px] font-bold text-text sm:text-[30px]">
              What should Argus watch for you?
            </h1>
            <p className="mt-2 text-[15px] leading-relaxed text-label">
              Say it like you'd say it to a friend. Include the page's address
              and what you're waiting for.
            </p>

            {atLimit && (
              <div className="mt-5 rounded-xl border border-amber/40 bg-[var(--amber-fill)] px-4 py-3">
                <p className="text-[14px] font-semibold text-text">
                  All {perUserLimit} of your watcher slots are in use
                </p>
                <p className="mt-1 text-[13.5px] leading-relaxed text-text2">
                  Delete one you no longer need and the slot frees up right
                  away.{" "}
                  <a href="/console" className="font-medium text-amber">
                    See my watchers
                  </a>
                </p>
              </div>
            )}

            {phase === "parsing" ? (
              /* The wait, made legible: the eye is working and says on what */
              <div className="mt-8 flex flex-col items-center gap-4 py-6 text-center">
                <WatchDial state="WATCHING" checking cadenceMinutes={60} />
                <div className="h-6">
                  <AnimatePresence mode="wait">
                    <motion.p
                      key={thought}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.25 }}
                      className="text-[14.5px] font-medium text-text2"
                    >
                      {THINKING[thought]}…
                    </motion.p>
                  </AnimatePresence>
                </div>
                <p className="text-[12.5px] text-muted">
                  This takes a few seconds.
                </p>
              </div>
            ) : (
              <div className="mt-6 space-y-4">
                <Textarea
                  value={sentence}
                  onChange={setSentence}
                  placeholder={'e.g. "Tell me when tickets go on sale on example.com/tickets"'}
                  rows={4}
                  aria-label="What should Argus watch for you?"
                />

                {/* Live reassurance, rather than an error after the fact */}
                <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                  <Hint ok={hasAddress}>A page address</Hint>
                  <Hint ok={hasWish}>What you're waiting for</Hint>
                </div>

                <div>
                  <p className="mb-2 text-[12.5px] font-medium text-muted">
                    Or start from one of these:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLES.map(([label, text]) => (
                      <button
                        key={label}
                        onClick={() => setSentence(text)}
                        className="rounded-full border border-line bg-panel px-3.5 py-2 text-[13px] font-medium text-label transition-colors hover:border-amber/50 hover:bg-panel2 hover:text-text"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {rejection && (
                  <div className="rounded-xl border border-red/50 bg-[rgba(255,107,129,0.06)] px-4 py-3">
                    <p className="text-[14px] font-semibold text-red">
                      That didn't quite work
                    </p>
                    <p className="mt-1 text-[13.5px] leading-relaxed text-text2">
                      {rejection}
                    </p>
                  </div>
                )}

                <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:items-center sm:gap-4">
                  <Button
                    type="button"
                    variant="primary"
                    onClick={parse}
                    disabled={!sentence.trim()}
                    className="w-full sm:w-auto"
                  >
                    Continue
                  </Button>
                  <a
                    href="/guide"
                    className="text-center text-[13.5px] text-label hover:text-text sm:text-left"
                  >
                    Tips for a good request
                  </a>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* -------------------------------- the moment it is being made */}
        {phase === "launching" && spec && (
          <motion.div
            key="launching"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col items-center gap-5 py-16 text-center"
          >
            <WatchDial state="WATCHING" checking cadenceMinutes={spec.cadence_minutes} />
            <div>
              <p className="font-display text-[20px] font-bold text-text">
                Setting {spec.callsign} on watch
              </p>
              <p className="mt-1.5 max-w-[38ch] text-[13.5px] leading-relaxed text-muted">
                Giving it its instructions, then sending it to read{" "}
                {hostOf(spec.url)} for the first time.
              </p>
            </div>
          </motion.div>
        )}

        {/* ---------------------------------------------------- step 2 */}
        {phase === "brief" && spec && (
          <motion.div
            key="brief"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.28, ease: [0.2, 0, 0, 1] }}
          >
            <h1 className="font-display text-[26px] font-bold text-text sm:text-[30px]">
              Here's the plan
            </h1>
            <p className="mt-2 text-[15px] leading-relaxed text-label">
              This is what Argus understood. Change anything that isn't right,
              then set it watching.
            </p>

            {/* What it will do, in one readable sentence */}
            <div className="mt-5 rounded-xl border border-line bg-panel2 px-4 py-3.5">
              <p className="text-[14.5px] leading-relaxed text-text2">
                Every <span className="font-semibold text-text">{spec.cadence_minutes} minutes</span>{" "}
                it will read{" "}
                <span className="font-semibold text-text">{hostOf(spec.url)}</span>{" "}
                and ask:{" "}
                <span className="italic text-text">“{spec.condition}”</span>
              </p>
            </div>

            <Panel className="mt-5">
              <div className="space-y-4">
                <Field
                  label="Name it"
                  value={spec.callsign}
                  onChange={setField("callsign")}
                  hint="How it appears in your list."
                />
                <Field label="Page to watch" value={spec.url} onChange={setField("url")} />
                <Textarea
                  label="What Argus looks for"
                  value={spec.condition}
                  onChange={setField("condition")}
                  rows={2}
                />
                <Field
                  label="Also keep track of (optional)"
                  value={spec.track || ""}
                  onChange={setField("track")}
                  placeholder="e.g. the current price"
                  hint="A value it writes down every visit, so you can see it move."
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    label="Check every (minutes)"
                    type="number"
                    value={spec.cadence_minutes}
                    onChange={(v) => setField("cadence_minutes")(Number(v))}
                    min={15}
                    max={1440}
                  />
                  <Field
                    label="Send alerts to"
                    type="email"
                    value={spec.email}
                    onChange={setField("email")}
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
                    checked={Boolean(spec.repeating)}
                    onChange={(v) => setField("repeating")(v)}
                  />
                </div>
              </div>

              {fleetFull && (
                <div className="mt-4 rounded-xl border border-red/50 bg-[rgba(255,107,129,0.06)] px-4 py-3">
                  <p className="text-[14px] font-semibold text-red">No free slots</p>
                  <p className="mt-1 text-[13.5px] leading-relaxed text-text2">
                    {fleetFull}{" "}
                    <a href="/console" className="font-medium text-amber">
                      See my watchers
                    </a>
                  </p>
                </div>
              )}

              <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
                {/* The launching state is its own screen now, so these are
                    only ever seen in their resting form. */}
                <Button
                  variant="primary"
                  onClick={launch}
                  className="w-full sm:w-auto"
                >
                  Start watching
                </Button>
                <Button variant="ghost" onClick={() => setPhase("command")}>
                  Go back and edit
                </Button>
              </div>
            </Panel>
          </motion.div>
        )}

        {/* ---------------------------------------------------- step 3 */}
        {phase === "done" && launched && (
          <motion.div
            key="done"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
            className="flex flex-col items-center gap-5 py-14 text-center"
          >
            <WatchDial state="WATCHING" cadenceMinutes={launched.cadence_minutes} />
            <div>
              <h1 className="font-display text-[26px] font-bold text-text sm:text-[30px]">
                {launched.callsign} is on watch
              </h1>
              <p className="mt-2 max-w-[42ch] text-[15px] leading-relaxed text-label">
                It is reading {hostOf(launched.url)} right now, and will keep
                looking every {launched.cadence_minutes} minutes. You'll get an
                email the moment it finds what you asked for.
              </p>
            </div>
            <p className="text-[12.5px] text-muted">Opening its page…</p>
          </motion.div>
        )}
      </AnimatePresence>
        </div>

        {/* Desktop only. On a phone the job is to write one sentence and
            press continue; guidance and inspiration below the fold is just
            scroll between someone and that. The chips already cover it. */}
        {showSidebar && (
          <div className="hidden lg:block">
            <Sidebar onPick={setSentence} />
          </div>
        )}
      </div>
    </main>
  );
}
