# Argus engineering log

The day-by-day record kept while building Argus: what was tried, what broke,
what was measured, and what was decided as a result. Preserved verbatim from
the working notes rather than tidied up, because the value is in the dead ends
and the wrong turns, not just the conclusions.

Read the [root README](../README.md) for the project itself. This is the
appendix.

---

## Progress log

**2026-07-22 (day 1).** Project scaffolded. All four providers verified live.
Commissioner implemented and tested end to end against real Supabase: "check
twice an hour" correctly became a 30 minute cadence, vague requests are
rewritten as testable yes/no questions, and non-watch requests are refused.
Audit pass fixed a silent Gemini outage masked by the Groq fallback, an SSRF
hole reachable via `/watchers/confirm`, a budget counter that committed on the
caller's session, and callsign collisions after retirement. Verified the
gitignore protects secrets, CORS is correct, and the day-2 tick claim SQL
works on real Postgres with no double-runs.

**2026-07-22 (day 2).** The Watcher role, the run loop and the mission log.
Probes now fetch a live page, judge it, quote evidence, and record the pass
with which model judged it. Verified against real sites: a true condition on
python.org triggered at confidence 100 with a quoted download line, a false
condition on example.com correctly did not trigger, and a full `/tick` pass
processed both. Added `MIN_USEFUL_CHARS` after finding that Amazon returns 142
characters of navigation chrome, which would have produced a confident but
meaningless verdict. Measured real-world fetch reliability at 7/10 sites.
Triggering is one-shot (fire, then stop) so a persistently true condition
cannot produce an alert storm; resume re-arms it.

**2026-07-23 (day 2 recheck).** Hardening pass before finalizing. Found and
fixed four bugs: (1) the SSRF guard could be bypassed via redirect, because
httpx auto-followed hops without re-validation; redirects are now manual and
every hop is checked, verified against live httpbin attacks. (2) The 1 MB
response cap sliced after download; now enforced while streaming. (3) The
tick claim SQL was Postgres-only, so a fresh clone on the SQLite fallback
would 500 on /tick; SQLite now gets an equivalent single-process path.
(4) run-now on an already-triggered probe emitted duplicate trigger events;
only active probes can fire now. Added the fetch escalation chain (TLS retry
for broken government certs, then the r.jina.ai rendering proxy) and measured
it: Pakistani gov and university sites went from 9/11 to 10/11 usable, with
NADRA rescued through its WAF. Considered and rejected self-hosted Playwright
rendering (too heavy for the 512 MB Koyeb instance) and an in-process
scheduler (dies when the free instance sleeps; external cron stays).

**2026-07-23 (day 3).** The Herald and real alert delivery. A triggered probe
now composes an alert with the Herald (Gemini 3.6 Flash) and sends it; verified
live end to end with a real email landing in the owner inbox, subject "PROBE-01:
Python 3.x release download link detected". The full sent message is stored as
an emailed event and exposed at `/watchers/{id}/transmissions`, so the app shows
the alert even if the email is filtered. Added `app/notify.py` as a channel
dispatcher with the WhatsApp channel (CallMeBot) implemented but dormant until
its env vars are set, and a deterministic Herald template fallback so an alert
survives an LLM failure.

**2026-07-23 (day 3, email polish).** Rebuilt the alert email. The Herald now
classifies each alert into one of five categories, each with its own HTML
design (`app/email_templates.py`) in the mission-control palette: availability
(green), price and generic (amber), release (blue), status (orange). Hardened
against injection: all values HTML-escaped, hrefs scheme-checked (a
`javascript:` link renders as a dead `#`), and subjects flattened to defeat
SMTP header injection. Verified with live `<script>`, `<img onerror>` and CRLF
attacks, and by emailing one live sample of every template. Removed the double
"Argus Mission Control" sign-off (the Herald no longer signs; the footer
does). Real trigger to real inbox still verified end to end.

**2026-07-23 (day 3, access + demo fleet).** Added the access gate and the
self-running demo, driven by how the site is actually graded: unattended, on
the grader's own time. One shared `ACCESS_CODE` gates the watcher API (frontend
prompts once, sends it as a header); `/demo/target` stays public. Seeded a
3-probe demo fleet on startup and a demo target page whose availability cycles
automatically, so a probe triggers on its own and the mission log is never
empty. Presence based (opening the site pulses the demo) plus a slow cron
baseline. Demo alerts are recorded and shown in-app but not emailed, so they do
not spam the owner inbox every cycle. The demo target is read straight from its
DB state (the SSRF guard would block an HTTP call to our own localhost URL, and
this avoids the round trip while keeping the AI judging real). 14/14 demo
checks pass, 17/17 core audit still green.

**2026-07-23 (day 3, honest-hybrid demo).** Reworked the demo for integrity
after a good question: was the auto-cycling demo a lie? Now the always-on fleet
watches only REAL sites (python.org, Wikipedia, Hacker News), so nothing in the
background is simulated. The synthetic appointment target is watched by a
single demo probe held in `standby` and excluded from the scheduler; it fires
only on `POST /demo/run` (the "Run a live demonstration" button), then resets
itself so it is repeatable. Both the target and the probe are labelled a
demonstration; the alert is shown in-app, never emailed. Also hardened startup:
a crashed local test left a session idle-in-transaction holding a lock, which
made `ALTER TABLE` in startup hang; the migration now sets a `lock_timeout` and
skips rather than hanging (production closes sessions cleanly via get_db, so it
never causes this itself). 10/10 hybrid checks pass.

**2026-07-23 (backend finalized).** Closed the gap that made Argus feel like a
notifier: agents now extract and track a data point every run, not just judge a
yes/no condition. The Commissioner pulls an optional `track` phrase from the
order ("keep track of the latest Python 3 version"), and the Watcher returns an
`extracted` value each run, logged over time. Verified live: an agent watching
python.org judged "is Python 4 out" as false while extracting "3.14.6" off the
page in the same pass. Also added a `/stats` fleet overview, a `/health` that
does a real DB round trip, and a committed pytest suite (23 tests, no keys or
network: SSRF, email injection, category selection, header injection, parsing).
23 unit + 17 core audit + 6 live tracking checks all green. Next: Koyeb deploy
+ cron, then the React frontend.

**2026-07-24 (local recheck, logo, email redesign).** Ran the real uvicorn
server and walked the whole API over live HTTP (22/22): Commissioner parse with
tracking, confirm, run-now with extraction, mission log, pause/resume, demo
target, on-demand demonstration, and the /tick heartbeat. Designed and added an
Argus logo (an all-seeing almond eye in an orbital ring with a probe; amber on
dark) via a committed generator (`tools/gen_logo.py` -> `assets/` +
`app/branding.py` data-URI, so the runtime needs no image library). Rebuilt the
alert email around it: logo header, category pill, a highlighted tracked-value
block (surfacing the extracted data point), evidence quote, and CTA. Kept the
injection hardening and added tests for it; 24 committed unit tests pass. Sent
one live sample of every category to confirm delivery. Pre-deploy note: reset
the Supabase tables so seeded callsigns start clean (test churn pushed ids up).

**2026-07-24 (hardening + adaptive orbits).** Review pass plus one new agentic
behavior. Hardening: the access-code check now uses a constant-time comparison,
the Watcher prompt treats page text as untrusted data (a page that tries to
instruct the model is ignored and the attempt is named in the reasoning), and
the fetcher docstring states the accepted DNS-rebinding residual risk honestly
instead of implying complete SSRF coverage. Then adaptive orbits: the Watcher
now also reports `changed` (did the page meaningfully move versus the previous
summary, ignoring cosmetic churn), and `plan_orbit` in tick.py turns that into
cadence autonomy anchored to the ordered cadence: a moving target tightens the
orbit to base/2, three calm passes relax it half-again-slower stepwise up to
base*4, all inside the global 15..1440 clamp. Every adjustment is an
`orbit_adjusted` event, `base_cadence_minutes` is exposed on WatcherOut so the
UI can show ORDERED vs CURRENT, and the demo probe and manual inspections of
non-active probes never adapt. Static pages now cost less budget and volatile
ones get watched harder, with no new dependencies. 34 unit tests pass (9 new
covering the orbit policy: floor, ceiling, streak reset, round trip).

**2026-07-25 (being a good guest, so we do not get blocked).** Audited what we
were doing to other people's servers and the answer was: almost nothing right.
A Chrome user-agent, no robots.txt, no rate limiting, no backoff, and the same
page fetched in full every single time. That is the exact profile that gets a
poller banned, and it is worth fixing before going public rather than after a
site blocks us.

Checked the guidance rather than guessing, and the shape of our traffic turns
out to matter: Argus is not a scraper crawling many pages once, it is a poller
hitting one page repeatedly, which is the pattern site owners notice most.
That makes conditional requests the single highest-value habit, and GitHub's
API documents 304 responses as not even counting against rate limits, so
servers actively reward it.

What changed. Identification is now honest: "Mozilla/5.0 (compatible;
ArgusWatcher/1.0; +url)", the conventional shape Googlebot uses, which says
what we are and where to complain. Spoofing Chrome would open a few more doors
but it removes the operator's ability to contact us and it is the behaviour
that drives sites toward blanket blocking. Tested against all six starter
targets before committing to it: 6/6 still readable, so the honest choice cost
nothing. robots.txt is fetched, cached for an hour, and obeyed, including
Crawl-delay, with a cap so one hostile value cannot stall a worker. Requests
to a single host are spaced out. A 429 or 503 is given the pause it asked for
in Retry-After and retried once instead of being hammered. And conditional
requests: the ETag and Last-Modified from each fetch are stored on the
watcher and sent back next time, so an unchanged page returns an empty 304,
costs the server almost nothing, and skips the model call entirely.

Two findings from testing. Hacker News declares Crawl-delay: 30 in robots.txt
and we had been ignoring it completely. And the 304 path works on real sites:
verified round trips against githubstatus.com and fpsc.gov.pk, both returning
not-modified on the second ask.

One subtlety the 304 shortcut created: a condition about timing ("closes
within a week") can turn true while the page sits perfectly still, so reusing
the previous verdict forever would miss it. A full re-read is therefore forced
every FULL_RECHECK_HOURS regardless of what the server says.

**2026-07-25 (pre-hosting pass on the cron path).** Exercised `/tick` end to
end for the first time, which matters because in production it is the thing
that makes Argus autonomous at all. It works: the secret is enforced, three
due watchers were claimed and processed, each rescheduled itself, and an
immediate second tick claimed nothing, so the atomic claim holds. But it took
23.9 seconds for three watchers, roughly eight seconds each of model latency,
and cron services time out well before that and start reporting the job as
failing. Restructured so the claim (the part that must not be lost) happens in
the request and the checks run after the response is sent: measured 0.74s to
respond, with the pass still completing and the watcher still rescheduling.
Also made ALLOWED_ORIGIN accept a comma separated list, since Vercel serves
preview deployments on their own hostnames and a single origin locks them out
of the API. Documented the deployment as a runbook rather than leaving it as a
line in the status section.

**2026-07-24 (silent-failure sweep, and a bug under every judgment).** Went
looking for gaps of the same shape as the recurring-watch one: things a user
would reasonably expect to work, that nobody had ever checked. Five fixes came
out of it, two of them affecting everything Argus does.

Confirmed broken and fixed: the Watcher had no clock. Asked whether a deadline
was within a week it answered "the present date is unknown to this probe",
which was at least honest, but every time-relative watch was dead: within a
week, before September, expired, older than three days. Today's date now goes
into the input. Verified on a deadline four days out (fires), one in November
(quiet), and an expiry already past (fires).

Over-long pages were being chopped at 32,000 characters in silence, so a name
in row 3,860 of a merit list read as a confident "not listed" while the
watcher looked perfectly healthy. Two changes: a page that gets cut now says
so in the text, and the prompt holds confidence to 40-60 on a negative verdict
when it sees that note, so a cut page can never produce a confident absence.
Then focused extraction: the watch condition and tracked field are passed to
the fetcher, distinctive terms are located in the FULL text, and windows
around them are kept along with the opening for context. A 203,000 character
merit list becomes 8,576 characters that actually contain the row in question.
The first version of this failed its own test, which is why the test exists:
terms were used in arbitrary order, so "roll" and "passed" (4,000 hits each)
exhausted the window budget before the roll number (1 hit) was ever looked up.
Rarest term first, and page furniture skipped once a real landmark is found.

A watcher that stops being able to read its page now says so. Three
consecutive failures sends one notice, in the alert shell with a red TROUBLE
accent, and the count resets on the next good pass so a later streak is
reported again. Verified against a domain that does not resolve: silent at one
and two failures, exactly one notice at three, still one at four.

The deepest find came from testing direction-specific movement ("only tell me
when it DROPS"). It failed on a 7,000 drop against a 5,000 threshold, and the
reasoning showed why: "the condition requires a drop of 5000 or more, wait,
412000 minus 405000 is 7000, which indeed equals or exceeds" and it still
answered false. The output schema had `met` before `reasoning`, so structured
output forced the model to commit to a verdict before working anything out,
leaving the reasoning as after-the-fact narration. Reordered so reasoning,
evidence and the extracted value come first and the verdict follows from them.
That was wrong under every judgment Argus has ever made, not just this case.
Retested 5/5 including the exact boundary, and swept the earlier scenarios for
regressions: 5/5 still correct.

Also verified, no changes needed: disappearance ("the Sold Out label is gone"),
percentage movement, compound AND/OR conditions, value format drift across a
redesign (PKR 412000 versus Rs. 412,000 versus 4.12 lakh all read as the same
number), new-item-in-a-list once the condition says to ignore the page's own
NEW badge, and PDF targets, which turn out to read fine.

**2026-07-24 (recurring watches: alert on every move, not once).** A rate has
no single moment you are waiting for, so the one-shot model could not express
"tell me whenever the dollar moves by a rupee". Two things were missing. The
Watcher only ever saw the current page plus a prose summary of last time, so
it had no reliable baseline to compare against: it now also receives PREVIOUS
TRACKED VALUE, which makes "has this moved by X" answerable, and the prompt
tells it to do the arithmetic honestly. And triggering was permanently
one-shot: watchers now carry a `repeating` flag, and a repeating watch re-arms
itself after alerting instead of standing down. Storms are prevented by the
shape of the condition rather than by a cooldown: the next comparison is
against the value it just reported, so the same move cannot fire twice. The
Commissioner decides the flag from the wording of the order ("whenever the
price changes" versus "when tickets go on sale") and both the launch brief and
the edit form expose it as a toggle.

Verified the model can actually do it before building the plumbing: 4 of 4
synthetic comparisons correct, including a rise, a fall, and two sub-threshold
moves correctly ignored. Then end to end on the live rate page, which found
two real bugs. First, the column was named last_value, which Postgres parses
as the window function of that name, so every watcher query failed to compile;
renamed to previous_value. Second, and more subtle, the re-arm silently did
nothing: the atomic trigger claim writes "triggered" straight to the row, so
assigning the attribute back to "active" restored its originally loaded value,
SQLAlchemy saw no change, emitted no UPDATE, and the row stayed triggered. A
recurring watch would have alerted exactly once and then quietly stopped
forever, looking healthy the whole time. Fixed with an explicit UPDATE and
re-verified by re-reading the row from the database rather than from memory.

**2026-07-24 (starter fleet replaced with six that earn their place).** The
seeded fleet was filler: "is Python 4 out" that can never fire, "is Islamabad
the capital" that is true forever, and a demo probe cluttering everyone's
list. Wiped the database (old seeds plus the test watchers made during
development) and rebuilt around watchers that are each genuinely useful AND
demonstrate a different capability: a dollar rate crossing a threshold with a
value charted over time, Python 3.15 going from pre-release to stable, a CSS
2027 exam announcement on FPSC, a GitHub outage, whether today's NASA picture
is about an exploding star, and security stories on a Hacker News front page
that moves fast enough to exercise the adaptive orbit. Every URL was fetched
and judged by hand first, and two candidates were rejected rather than shipped
hopefully: pakbonds.com rotates its countdown between denominations so a
Rs. 1500 watch is a coin flip, and the PSX index page loses its labels in
extraction so the model cannot tell which number is the KSE-100. Verified all
six through the real run-now path: 6/6 extracted a tracked value, four sit
correctly pending, and NASA and Hacker News both fired correctly on live
content. Starters are seeded paused, shared and facility owned, and the list
endpoint no longer mixes them into anyone's own list. That last part fixed a
genuine design fault: pressing Resume on a facility watcher would have run it
for every user at once and sent its alerts to the facility address rather than
to whoever pressed the button. They now live only in the Shared tab, where the
action is "use this watcher", which clones it into your fleet with your email.
The demo probe is hidden from all lists but still powers the demo button.

**2026-07-24 (confidence made to mean something).** Checked the stored runs
before defending the number and the data was damning: 9 of 10 judged passes
returned exactly 100, one returned 95, mean 99.5, nothing ever near the 70
gate. The prompt had asked for "how sure you are" with no definition, which is
the classic way to get a meaningless self-report. Added a rubric with bands
anchored to what the page shows (95-100 settles it outright and you quoted the
deciding words, 80-94 read from context or a paraphrase, 70-79 ambiguous or
truncated, 40-69 points both ways, 0-39 nothing to judge with). The first
attempt made things worse and exposed the real defect: the model was rating
its confidence in the VERDICT while the rubric was written as "how clearly
does the page state the thing", so an absent subject scored a confident 100
for false and the number was incoherent across polarities. Fixed by defining
it explicitly as confidence in the verdict either way, with a note that a page
which mentions the subject but never resolves it belongs in the middle bands.
Measured on five graded page texts: states-it-outright 100 met, paraphrase 75
not met, unresolved 100 not met, subject-absent 100 not met, truncated 95 not
met. The number now moves and reads coherently. Keeping it rather than
dropping it because it is load-bearing: TRIGGER_CONFIDENCE refuses to fire
below 70 regardless of what the prompt says. Standing caveat recorded here so
nobody oversells it later: this is a model self-report, not a calibrated
probability, and 100 does not mean wrong zero times in a hundred. The UI now
says as much on hover. Also deleted two components the details-page declutter
had orphaned (Confidence.jsx, CountRoll.jsx).

**2026-07-24 (per-category alert designs restored, plus phone rules).**
Reversed an earlier decision. The 2026-07-24 redesign collapsed the five
per-category email designs into one on a "single accent, no rainbow" rule,
after which `category` only changed two words. That rule is right for the web
app, where many elements share a screen, and wrong for email, where you see
one alert at a time and colour is how an inbox gets triaged. Each category is
now its own kind of star: availability green, price gold, release blue white,
status violet, generic neutral starlight, each with its own glyph and status
line. The split of duties keeps it disciplined rather than a rainbow: the
accent owns the news (top rule, header sky tint, status line, tracked-value
readout, evidence rule, lit star) while amber stays the interface colour
(section labels, action button), so every alert still reads as Argus. Tests
now assert each category's accent and glyph render, that all five are unique,
and that amber survives on the CTA. Also made the email genuinely responsive:
it was fluid (max-width plus width:100%) but had no media queries, so a 320px
screen lost a fifth of its width to gutters. Added phone rules that tighten
gutters to 18px, scale the headline and readout down, drop the header tagline
rather than crushing it, and shrink telemetry type, with the fluid shell still
carrying clients that ignore media queries. Added a hidden preheader so the
inbox preview shows the news instead of the wordmark.

**2026-07-24 (Herald rewrite: alerts that say one thing).** Read the alerts
actually landing in the inbox and found them padded: every one restated the
setup ("PROBE-70 was monitoring <url> for..."), repeated the URL the template
already shows, introduced the quote with "the evidence captured states", and
ended on a limp "please visit the page now" even though the email has a
button. Four sentences to deliver one fact. Rewrote HERALD_PROMPT around a
hard shape (subject = the news itself under 60 chars including the key value;
body = one or two sentences, 40 words max, lead with the concrete fact then
stop) plus an explicit list of banned moves: no restating the setup, no naming
the watcher or repeating the URL, no "evidence states" preamble, no call to
action, no passive bureaucratic phrasing. The deterministic fallback was
rewritten in the same voice. Measured on the three real alerts already sent:
bodies went from 45-55 words to 9-18, e.g. "The probe was monitoring
https://pakbonds.com for the next 1500 prize bond draw date. A date for the
Rs. 1,500 draw has now been listed... Please visit the page promptly to review
the details." became "The next Rs. 1,500 prize bond draw is listed for August
15, 2026." Subjects now lead with the news rather than a meaningless callsign
prefix. Also softened two template strings the reader actually reads (OPEN
TARGET -> OPEN THE PAGE, and the transmission/probe footer line) so the email
voice matches the app's plain language.

**2026-07-24 (deep read + instant first check).** Two changes that came out of
a real failed test: a watcher on pakbonds.com could not see the site's next
draw date because it lives in a JavaScript countdown, invisible to static
extraction. First, found and fixed a live bug: r.jina.ai (the JS-rendering
proxy) sits behind Cloudflare and 403s browser-looking User-Agents, so the
rendering fallback had been silently returning nothing; it now sends no UA and
works. Second, built deep read: when a pass reads the page fine but the
tracked value is missing from the static text, the watcher re-fetches through
the renderer and re-judges once; if the rendered text surfaces the data it
adopts that verdict, marks the reasoning "[deep read]", logs a deep_read
event, and sets use_renderer on the watcher so future passes render first.
The probe learns how to read its target. Verified live end to end: PROBE-Pak
extracted "Aug 15, 2026" off the pakbonds.com countdown at confidence 100,
triggered, and delivered a real alert email. Third, instant first check: on
/watchers/confirm the first pass now runs as a FastAPI background task, so
launching a watcher produces a real verdict within seconds instead of silence
until the next cron tick (also fixes local dev, which has no cron). All 34
tests pass.

**2026-07-24 (email fix + redesign).** Fixed the logo not rendering: Gmail
strips `data:` image URLs, so the logo is now an inline CID attachment
(multipart/related), which clients render. Then rebuilt the alert email to stop
looking like a generic SaaS card and commit to the Deep Space Mission Control
brand: near-black console panel, a single amber accent with verdict green used
once for the status line, hairline borders, monospace telemetry, `// SECTION`
markers, a `KEY : value` TELEMETRY readout (probe, confidence, tracked value,
target, class), an EVIDENCE quote, and an outline monospace CTA rather than a
solid rounded button. Data-dense and left-aligned, not soft and centred. 25
committed unit tests pass. Added GET /logo.png to serve the mark.
