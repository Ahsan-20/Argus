import { motion } from "framer-motion";
import { Panel } from "../components/Panel.jsx";
import { Button } from "../components/Button.jsx";
import { OrbitMap } from "../components/OrbitMap.jsx";
import { Logo } from "../components/Logo.jsx";
import { TopBar } from "../components/TopBar.jsx";
import { useStats } from "../hooks/useQueries.js";
import { useSession } from "../state/session.jsx";
import { usePrefs } from "../state/prefs.jsx";
import { useTitle } from "../hooks/useTitle.js";

// Decorative watchers for the hero orbit (a visual, not fake data — the real
// numbers below come from the live /stats endpoint).
// Named the way real watchers are named, not PROBE-NN: the labels are visible
// in the hero, so leaving jargon here would contradict the whole product.
const HERO_PROBES = [
  { id: 1, callsign: "Dollar rate", cadence_minutes: 20, status: "active" },
  { id: 2, callsign: "Prize bond draw", cadence_minutes: 90, status: "triggered" },
  { id: 4, callsign: "Exam results", cadence_minutes: 240, status: "active" },
  { id: 7, callsign: "Visa slots", cadence_minutes: 45, status: "paused" },
  { id: 9, callsign: "Ticket sale", cadence_minutes: 600, status: "active" },
];

// Sections rise into place as they come into view. Skipped entirely in calm
// mode, where the content simply appears.
function Reveal({ children, className = "" }) {
  const { reducedMotion } = usePrefs();
  if (reducedMotion) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, ease: [0.2, 0, 0, 1] }}
    >
      {children}
    </motion.div>
  );
}

const CLEVER = [
  [
    "It tunes its own schedule",
    "A page that keeps changing gets checked more often. A page that never moves gets checked less. You set the starting pace, it adjusts from there.",
  ],
  [
    "It shows you its evidence",
    "Every check records the verdict, how sure it was, and a quote from the page. You never have to take its word for anything.",
  ],
  [
    "It can follow a number",
    "Ask it to track a price, a rate, or a count and it writes the value down each visit, then charts it. Useful long before your condition is met.",
  ],
  [
    "It can tell you every time",
    "Waiting for one event? It alerts once and stands down. Watching a rate? Ask it to report every move instead.",
  ],
];

function Step({ n, title, body }) {
  return (
    <div
      className="rounded-2xl border border-line bg-panel p-5"
      style={{ boxShadow: "var(--card-shadow)" }}
    >
      <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--amber-fill)] font-display text-[14px] font-bold text-amber">
        {n}
      </span>
      <h3 className="mt-3 font-display text-[17px] font-semibold text-text">
        {title}
      </h3>
      <p className="mt-1.5 text-[14px] leading-relaxed text-label">{body}</p>
    </div>
  );
}

export default function Landing() {
  useTitle(null);
  const stats = useStats();
  const { signedIn } = useSession();
  const online = stats.data && !stats.isError;
  // A signed-in visitor's "get started" is their dashboard, not the gate.
  const startTo = signedIn ? "/console" : "/signup";
  const startLabel = signedIn ? "Open your dashboard" : "Get started";

  return (
    <div className="relative">
      <TopBar />

      {/* Hero */}
      <section className="mx-auto grid max-w-[1200px] items-center gap-8 px-4 pt-10 pb-12 sm:pt-14 sm:pb-16 lg:grid-cols-2 lg:gap-10">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
        >
          <h1 className="font-display text-[34px] font-bold leading-[1.12] text-text sm:text-[44px] lg:text-[50px]">
            Stop refreshing.
            <br />
            <span className="text-amber">Argus watches the page for you.</span>
          </h1>
          <p className="measure mt-5 text-[15.5px] leading-relaxed text-text2 sm:text-[16.5px]">
            Waiting for tickets, a visa appointment, a restock, a result?
            Tell Argus in one plain sentence. It checks the page for you, around
            the clock, and alerts you the moment it happens.
          </p>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button to={startTo} variant="primary" size="lg" className="w-full sm:w-auto">
              {startLabel}
            </Button>
            <Button to="/guide" variant="secondary" size="lg" className="w-full sm:w-auto">
              How it works
            </Button>
          </div>

          {/* Live numbers from the real service */}
          {online && (
            <p className="mt-8 border-t border-line pt-4 text-[13px] text-label sm:text-[13.5px]">
              Right now:{" "}
              <span className="font-semibold text-text2">
                {/* The count of watchers actually on duty, not every watcher
                    that exists. Those differ now that the shared starter
                    watchers arrive paused, waiting to be switched on, and
                    "on duty" has to mean what it says. */}
                {stats.data.by_status?.active ?? 0} watchers
              </span>{" "}
              on duty ·{" "}
              <span className="font-semibold text-text2">
                {stats.data.total_runs.toLocaleString()} checks
              </span>{" "}
              made ·{" "}
              <span className="font-semibold text-text2">
                {stats.data.positive_verdicts} finds
              </span>
            </p>
          )}
        </motion.div>

        {/* The living sky: full-size on desktop, compact (not gone) on phones.
            Story chips fade in and out, acting out what Argus does. */}
        <div className="relative flex items-center justify-center">
          <div className="relative hidden lg:block">
            <OrbitMap watchers={HERO_PROBES} callsign="you" />
            <span className="hero-chip" style={{ top: "14%", right: "-2%" }}>
              <span className="h-1.5 w-1.5 rounded-full bg-green" />
              Found it, alert sent
            </span>
            <span
              className="hero-chip"
              style={{ bottom: "18%", left: "-4%", animationDelay: "5.5s" }}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-amber" />
              Checking the page…
            </span>
            <span
              className="hero-chip"
              style={{ top: "48%", right: "-10%", animationDelay: "8.5s" }}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-steel" />
              Nothing new · next check 30 min
            </span>
          </div>
          <div className="relative block w-full max-w-[340px] lg:hidden">
            <OrbitMap watchers={HERO_PROBES} callsign="you" compact />
            <span className="hero-chip" style={{ top: "6%", right: "0" }}>
              <span className="h-1.5 w-1.5 rounded-full bg-green" />
              Found it, alert sent
            </span>
            <span
              className="hero-chip"
              style={{ bottom: "8%", left: "0", animationDelay: "5.5s" }}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-amber" />
              Checking the page…
            </span>
          </div>
        </div>
      </section>

      {/* The problem */}
      <Reveal className="mx-auto max-w-[1200px] px-4 py-8 sm:py-10">
        <p className="measure font-display text-[19px] font-semibold leading-snug text-text sm:text-[22px]">
          You know the feeling: checking the same page ten times a day, afraid
          to miss the moment. That's a job for a machine. A patient one.
        </p>
      </Reveal>

      {/* How it works */}
      <Reveal className="mx-auto max-w-[1200px] px-4 py-8 sm:py-10">
        <h2 className="font-display text-[24px] font-bold text-text sm:text-[26px]">
          Three steps, one sentence
        </h2>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <Step
            n="1"
            title="Say what you're waiting for"
            body={`Like "Tell me when tickets go on sale on this page." Argus reads your sentence and sets everything up.`}
          />
          <Step
            n="2"
            title="Argus keeps checking"
            body="It visits the page on a schedule, reads it like a person would, and decides whether your moment has arrived."
          />
          <Step
            n="3"
            title="You get the alert"
            body="The instant it happens, you get an email with what changed and proof from the page. Then you act."
          />
        </div>
      </Reveal>

      {/* A real example */}
      <Reveal className="mx-auto max-w-[1200px] px-4 py-8 sm:py-10">
        <div className="grid gap-4 md:grid-cols-2">
          <Panel title="You say">
            <p className="text-[15px] leading-relaxed text-text2">
              “Watch this page and tell me when an appointment slot before
              September opens up.”
            </p>
          </Panel>
          <Panel title="Argus replies (when it happens)">
            <p className="font-display text-[15.5px] font-semibold text-text">
              An appointment slot before September is open
            </p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-label">
              Seen on the page: “2 slots available for booking” · 94% sure ·
              checked 2 minutes ago
            </p>
          </Panel>
        </div>
      </Reveal>

      {/* Honesty */}
      <Reveal className="mx-auto max-w-[1200px] px-4 py-8 sm:py-10">
        <h2 className="font-display text-[20px] font-bold text-text sm:text-[22px]">
          Fair warning, in plain words
        </h2>
        <p className="measure mt-3 text-[15px] leading-relaxed text-text2">
          Argus works on public web pages. If what you want only appears once
          the page finishes loading, like a countdown or a live price, it takes
          a second look with the scripts run and reads it anyway. Pages behind a
          login are genuinely out of reach, and a few sites turn away anything
          automated. When a page can't be read, Argus says exactly that rather
          than guessing.
        </p>
      </Reveal>

      {/* The parts worth knowing about, none of which fit in "three steps" */}
      <Reveal className="mx-auto max-w-[1200px] px-4 py-8 sm:py-10">
        <h2 className="font-display text-[24px] font-bold text-text sm:text-[26px]">
          It is a little cleverer than a reminder
        </h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {CLEVER.map(([title, body]) => (
            <div
              key={title}
              className="rounded-2xl border border-line bg-panel p-5"
              style={{ boxShadow: "var(--card-shadow)" }}
            >
              <h3 className="font-display text-[16px] font-semibold text-text">
                {title}
              </h3>
              <p className="mt-1.5 text-[14px] leading-relaxed text-label">
                {body}
              </p>
            </div>
          ))}
        </div>
      </Reveal>

      {/* Bottom call to action */}
      <section className="mx-auto max-w-[1200px] px-4 py-10">
        <div
          className="flex flex-col items-center gap-4 rounded-2xl border border-line bg-panel px-6 py-10 text-center"
          style={{ boxShadow: "var(--card-shadow)" }}
        >
          <h2 className="font-display text-[24px] font-bold text-text">
            Let Argus take the night shift
          </h2>
          <p className="measure text-[14.5px] text-label">
            Set up your first watcher in under a minute.
          </p>
          <Button to={startTo} variant="primary" size="lg">
            {startLabel}
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="mx-auto max-w-[1200px] border-t border-line px-4 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <Logo size={22} />
            <span className="text-[13px] text-muted">
              Argus · always watching, so you don't have to · v0.1.0
            </span>
          </div>
          {/* The "Source code" link used to point at github.com itself, which
              is not a repository and told a visitor nothing. Put it back with
              the real repository address once there is one. */}
          <a href="/guide" className="text-[13px] text-label hover:text-text">
            How it works
          </a>
        </div>
      </footer>
    </div>
  );
}
