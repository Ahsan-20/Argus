import { motion } from "framer-motion";
import { Panel } from "../components/Panel.jsx";
import { Button } from "../components/Button.jsx";
import { Reveal } from "../components/Reveal.jsx";
import { usePrefs } from "../state/prefs.jsx";
import { useTitle } from "../hooks/useTitle.js";

// How it works: written to be read straight down, once, by someone who has
// never seen the app. Everything here is either something you have to know to
// use it, or something people actually ask. Anything else belongs on the page
// it describes, not in a manual.

function Faq({ q, children }) {
  return (
    <details className="group border-b border-line last:border-b-0">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-[14.5px] font-semibold text-text hover:bg-raised/30 [&::-webkit-details-marker]:hidden">
        {q}
        <span className="shrink-0 text-label transition-transform group-open:rotate-180">
          ▾
        </span>
      </summary>
      <div className="px-5 pb-4 text-[14px] leading-relaxed text-text2">
        {children}
      </div>
    </details>
  );
}

// One stage of a watcher's life. The dot for the stage a watcher spends its
// time in keeps a slow pulse, so the diagram reads as a thing in motion rather
// than a static key. The rest sit still, which is the point being made.
function Stage({ color, title, body, last, alive }) {
  const { reducedMotion } = usePrefs();
  return (
    <div className="flex flex-1 gap-3 sm:block">
      <div className="flex shrink-0 flex-col items-center sm:flex-row">
        <span
          className={`mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full sm:mt-0${
            alive && !reducedMotion ? " guide-pulse" : ""
          }`}
          style={{ backgroundColor: color }}
        />
        <span
          className="my-1 w-px flex-1 sm:my-0 sm:mx-2 sm:h-px sm:w-full"
          style={{ background: last ? "transparent" : "var(--color-line)" }}
        />
      </div>
      <div className="pb-4 sm:pb-0 sm:pt-3">
        <p className="text-[14.5px] font-semibold text-text">{title}</p>
        <p className="mt-0.5 text-[13px] leading-relaxed text-label">{body}</p>
      </div>
    </div>
  );
}

const STEPS = [
  [
    "Press “Watch something new”",
    "The gold button on your watchers page. “New” in the header does the same thing.",
  ],
  [
    "Say what you are waiting for, in one sentence",
    "Include the page address and the thing you want. For example: “Tell me when tickets go on sale on example.com/tickets.”",
  ],
  [
    "Check what it understood, then start it",
    "Argus shows you its plan so you can fix anything it got wrong. It then checks the page straight away, so you see a real result in seconds.",
  ],
];

const IDEAS = [
  ["Results and notices", "Exam results, merit lists, job adverts, tender boards"],
  ["Money", "Gold and exchange rates, a price you are waiting to drop, fee schedules"],
  ["Availability", "Appointment and visa slots, restocks, tickets going on sale"],
  ["Releases", "New software versions, blog posts, a mention of your name or company"],
];

export default function Guide() {
  useTitle("How it works");
  return (
    <main className="mx-auto max-w-[720px] px-4 py-8 sm:py-10">
      {/* On mount, not on scroll: this is already on screen, so waiting for it
          to be scrolled into view would just mean showing nothing. */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
      >
        <h1 className="font-display text-[26px] font-bold text-text sm:text-[30px]">
          How it works
        </h1>
        <p className="mt-1 text-[15px] text-label">
          A short read, top to bottom. No jargon.
        </p>
      </motion.div>

      <Panel className="mt-6">
        <p className="text-[15px] leading-relaxed text-text2">
          <span className="font-semibold text-text">
            Argus watches a web page so you do not have to.
          </span>{" "}
          You tell it what you are waiting for. It checks the page on a
          schedule, reads it the way a person would, and emails you the moment
          it happens, including at 3am while you are asleep.
        </p>
      </Panel>

      {/* Three steps */}
      <Reveal as="section" className="mt-9">
        <h2 className="font-display text-[20px] font-bold text-text">
          Setting one up
        </h2>
        <ol className="mt-4 space-y-3">
          {STEPS.map(([title, body], i) => (
            <li
              key={title}
              className="flex gap-4 rounded-2xl border border-line bg-panel p-4"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--amber-fill)] font-display text-[14px] font-bold text-amber">
                {i + 1}
              </span>
              <div>
                <p className="text-[14.5px] font-semibold text-text">{title}</p>
                <p className="mt-0.5 text-[13.5px] leading-relaxed text-label">
                  {body}
                </p>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button to="/launch" variant="primary">
            Set up a watcher
          </Button>
          <span className="text-[13px] text-muted">
            Or copy one that is already running from the Shared tab.
          </span>
        </div>
      </Reveal>

      {/* Writing the sentence */}
      <Reveal as="section" className="mt-10">
        <h2 className="font-display text-[20px] font-bold text-text">
          Writing a good sentence
        </h2>
        <p className="mt-2 text-[14.5px] leading-relaxed text-text2">
          Say <span className="font-semibold text-text">which page</span> and{" "}
          <span className="font-semibold text-text">what you are waiting for</span>
          . Being specific is the whole trick.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-green/40 bg-panel p-4">
            <p className="text-[12.5px] font-semibold text-green">Good</p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-text2">
              "Watch x-rates.com and tell me when the dollar to rupee rate moves
              by 1 rupee or more. Also track the rate."
            </p>
          </div>
          <div className="rounded-2xl border border-line bg-panel p-4">
            <p className="text-[12.5px] font-semibold text-muted">Too vague</p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">
              "Let me know if the dollar changes."
            </p>
          </div>
        </div>
        <ul className="mt-4 space-y-2.5">
          {[
            [
              "Ask it to follow a number",
              "Add “and track the rate” or “track the price”. Argus writes that number down every visit and draws you a chart of it.",
            ],
            [
              "Give it one page, not a whole website",
              "Argus watches the address you give it. So search the shop yourself first, then hand it the results page or the product page.",
            ],
          ].map(([t, b]) => (
            <li key={t} className="flex gap-2.5">
              <span className="mt-[9px] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
              <p className="text-[13.5px] leading-relaxed text-label">
                <span className="font-semibold text-text">{t}.</span> {b}
              </p>
            </li>
          ))}
        </ul>
      </Reveal>

      {/* Lifecycle */}
      <Reveal as="section" className="mt-10">
        <h2 className="font-display text-[20px] font-bold text-text">
          What happens next
        </h2>
        <p className="mt-2 text-[14.5px] leading-relaxed text-text2">
          Worth knowing, because it explains why the emails stop.
        </p>
        <div
          className="mt-4 rounded-2xl border border-line bg-panel p-5"
          style={{ boxShadow: "var(--card-shadow)" }}
        >
          <div className="sm:flex sm:gap-2">
            <Stage
              color="var(--color-amber)"
              title="Watching"
              body="It checks on schedule and writes down every visit."
              alive
            />
            <Stage
              color="var(--color-green)"
              title="Found it"
              body="Your thing happens. It emails you once, with proof from the page."
            />
            <Stage
              color="var(--color-steel)"
              title="Stops"
              body="It stands down, so one event cannot flood your inbox."
              last
            />
          </div>
          <p className="mt-4 border-t border-line pt-4 text-[13.5px] leading-relaxed text-label">
            Press <span className="font-semibold text-text">Resume watching</span>{" "}
            to put it back on duty. You can also{" "}
            <span className="font-semibold text-text">Check now</span> to make it
            look right away, <span className="font-semibold text-text">Pause</span>{" "}
            it, or <span className="font-semibold text-text">Edit</span> anything
            about it later.
          </p>
        </div>

        <div className="mt-3 rounded-2xl border border-amber/30 bg-panel p-4">
          <p className="text-[13.5px] font-semibold text-text">
            Unless you want it to keep going
          </p>
          <p className="mt-1 text-[13.5px] leading-relaxed text-label">
            Following a price or a rate rather than waiting for one event? Turn
            on{" "}
            <span className="font-semibold text-text">
              "Keep telling me every time"
            </span>
            . Then it never stops: it tells you about the move, remembers the new
            number, and goes straight back to watching for the next one.
          </p>
        </div>
      </Reveal>

      {/* Ideas */}
      <Reveal as="section" className="mt-10">
        <h2 className="font-display text-[20px] font-bold text-text">
          Things worth watching
        </h2>
        <p className="mt-2 text-[14.5px] leading-relaxed text-text2">
          Anything you catch yourself refreshing.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {IDEAS.map(([tag, items], i) => (
            <Reveal
              key={tag}
              delay={i * 0.07}
              className="rounded-2xl border border-line bg-panel p-4 transition-colors hover:border-lineb"
            >
              <p className="text-[12.5px] font-semibold text-amber">{tag}</p>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-text2">
                {items}
              </p>
            </Reveal>
          ))}
        </div>
        <p className="mt-4 text-[13.5px] leading-relaxed text-label">
          Made something useful? Turn on{" "}
          <span className="font-semibold text-text">Share with everyone</span> on
          its page and it appears in the Shared tab for other people. They get
          their own copy, with their own alerts. Yours stays private.
        </p>
      </Reveal>

      {/* Questions */}
      <Reveal as="section" className="mt-10">
        <h2 className="font-display text-[20px] font-bold text-text">
          Questions
        </h2>
        <div
          className="mt-4 overflow-hidden rounded-2xl border border-line bg-panel"
          style={{ boxShadow: "var(--card-shadow)" }}
        >
          <Faq q="How often does it check?">
            You choose, from every 15 minutes to once a day. When a check finds
            your thing, the email goes out within seconds, so the wait is really
            the gap between checks. It also tunes itself: a page that keeps
            changing gets checked more often, one that never changes gets checked
            less.
          </Faq>
          <Faq q="Will it keep emailing me over and over?">
            No. It emails once, then stops and moves to your Found tab. If you
            actually want every move, turn on "Keep telling me every time".
          </Faq>
          <Faq q="What pages can it watch?">
            Public ones: news, government portals, university pages, release and
            listing pages. Anything behind a login is out of reach. If what you
            want only shows up once the page has finished loading, Argus takes a
            second look and reads it anyway. When a page cannot be read, it tells
            you that instead of guessing.
          </Faq>
          <Faq q="What if the page breaks?">
            It keeps trying, and emails you after three failures in a row, so a
            watcher can never sit there quietly broken while you wait on it.
          </Faq>
          <Faq q="What if I miss the email?">
            Every alert is also saved on the watcher's own page, exactly as it
            was sent.
          </Faq>
          <Faq q="Do I need an account? Does it cost anything?">
            No to both. The access code and your email is all it takes. Argus
            runs on free services, so there are limits: 5 watchers each, 25
            across the whole site. It keeps your email address and the text it
            reads from public pages. No passwords, no tracking.
          </Faq>
          <Faq q="Is it a nuisance to the sites it watches?">
            No, and that is deliberate. It says who it is rather than pretending
            to be a person, obeys each site's rules about where automated
            visitors may go and how long to wait between visits, spaces out its
            own visits, and waits when a server says it is busy. Where a site
            supports it, Argus asks "has this changed since I last looked?" and
            skips the read entirely when the answer is no.
          </Faq>
          <Faq q="What is actually doing the reading?">
            Three AI roles. One turns your sentence into a precise watch. One
            reads the page on every visit and decides, giving a confidence score
            and a quote as evidence. One writes the alert. If the main AI service
            is busy, Argus falls back to another one so your watchers keep
            running.
          </Faq>
        </div>
      </Reveal>

      <div className="mt-10 flex flex-col items-center gap-3 rounded-2xl border border-line bg-panel px-6 py-8 text-center">
        <p className="font-display text-[18px] font-semibold text-text">
          Ready to stop refreshing?
        </p>
        <Button to="/launch" variant="primary">
          Watch something new
        </Button>
      </div>
    </main>
  );
}
