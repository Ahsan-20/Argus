# Argus - Backend

> **Working notes, not the final README.** This is our shared memory for the
> project: decisions, gotchas, and status. Keep it updated as we go. A polished
> public version gets written at the end, once everything ships.

An agent factory you command in plain English. One sentence becomes an
autonomous probe that watches a web page on a schedule, reasons about whether
your condition is met, and emails you the moment it is.

Frontend lives in a separate repository.

---

## Status

**Backend finalized (2026-07-23). Agents extract data, not just notify.**

Working:
- FastAPI app on Supabase Postgres, tables auto-create on startup
- LLM client with escalation: Gemini primary, backup Gemini model, then Groq
- Daily LLM budget counter tracked in the database
- **The Commissioner**: plain English becomes a structured watcher spec
- **The Watcher**: fetches a live page and returns a verdict with confidence,
  a quoted evidence line, mission-log reasoning, AND extracts a tracked data
  point (e.g. a price, a version, a count) so the agent produces output over
  time, not just a yes/no alert
- **The Herald**: on a trigger, writes the alert (subject + body), with a
  deterministic template fallback if the model hiccups
- **Real alert delivery**: a triggered probe emails the user (verified live to
  a real inbox), and the full sent message is stored and viewable in-app
- Notification dispatcher with a WhatsApp channel (CallMeBot) implemented and
  gated off until its two env vars are set
- Full run loop: `/tick` claims due probes, runs each, stores the pass
- Mission log and transmissions per probe, run-now for instant demos
- One-shot triggering: a probe fires once then stops, resume re-arms it
- Watcher management: create, confirm, list, get, pause, resume, retire
- SSRF guard enforced at watcher creation, redirects re-validated per hop
- **Access gate**: the whole watcher API sits behind a shared access code
- **Real seeded fleet**: 3 probes watching genuine sites (python.org,
  Wikipedia, Hacker News) so the deployed dashboard is populated and honest
- **On-demand demonstration**: a single labelled demo probe that fires only
  when a user presses "Run a live demonstration", against a synthetic target
- **Fleet stats** and a **DB-checked health** endpoint for the dashboard/deploy
- **Committed unit tests** (`tests/`, run with pytest, no keys needed)

Next: deploy to Koyeb + cron, then the React frontend on Vercel.

---

## How it works

No background daemon. An external cron (cron-job.org) POSTs `/tick` every ~5
minutes, which both drives the schedule and keeps the free Koyeb instance awake.

```
cron -> POST /tick -> claim due watchers (atomic)
                   -> fetch page (httpx + trafilatura, SSRF guarded)
                   -> Watcher LLM judges: met? confidence? evidence?
                   -> store the run in the mission log
                   -> if met: Herald writes the alert -> SMTP -> user
```

| Module | Purpose |
|---|---|
| `app/main.py` | FastAPI app, CORS, health, secured `/tick` |
| `app/config.py` | All settings and secrets (pydantic-settings) |
| `app/db.py` | Supabase engine, SQLite fallback for fresh clones |
| `app/models.py` | Watcher, Run, Event, BudgetCounter, DemoState |
| `app/schemas.py` | API request/response models |
| `app/prompts.py` | The three system prompts (single source of truth) |
| `app/llm.py` | Provider escalation, JSON output, budget tracking |
| `app/fetcher.py` | Page fetch + readable extraction + SSRF guard |
| `app/tick.py` | Scheduler: atomic claim + run loop |
| `app/mailer.py` | SMTP alert delivery |
| `app/notify.py` | Channel dispatcher: email now, WhatsApp when enabled |
| `app/email_templates.py` | Injection-safe HTML alerts, one style per category |
| `app/branding.py` | Generated logo data-URI embedded in emails |
| `tools/gen_logo.py` | Logo asset generator (dev only, needs Pillow) |
| `assets/` | Logo PNGs (mark, app tile, email) |
| `app/demo.py` | Demo target page, auto-cycle, seed fleet |
| `app/deps.py` | Shared access-code dependency |
| `app/routers/watchers.py` | Commissioner flow and fleet management |
| `app/routers/demo.py` | Demo target page and on-demand demonstration |
| `tests/` | Committed, CI-safe unit tests (no keys or network) |

### The three AI roles

All prompts live in `app/prompts.py` and are printed in full in the final
README (a grading requirement). Never inline a prompt anywhere else.

1. **The Commissioner** turns a sentence into a testable watcher spec, or refuses.
2. **The Watcher** judges one fetch against the condition and returns a verdict
   with confidence, evidence and reasoning. It also extracts an optional
   tracked data point (the price, the version, the count the user asked to
   follow), which is logged each run so the agent builds a record over time.
   This is what makes each probe an autonomous worker rather than a
   change-notifier: it reads, reasons, extracts, and acts.
3. **The Herald** writes the alert (subject + body) once a probe triggers, and
   classifies it into a category (availability, price, release, status,
   generic). A deterministic template is used if the model call fails, so an
   alert is never lost to an LLM hiccup.

The category selects one of five HTML email designs (`app/email_templates.py`),
each with its own accent and badge, all in the mission-control palette. The
templates are hardened: every dynamic value is HTML-escaped, hrefs are
scheme-checked so a model-supplied `javascript:` link cannot render live, and
subjects are flattened to one line so a crafted value cannot inject SMTP
headers. Verified with live injection attempts.

Alerts go out through a notification dispatcher (`app/notify.py`) so channels
are decoupled from the trigger. Email is always on. WhatsApp (via CallMeBot,
free and keyless) is implemented and turns on when its two env vars are set.
Each channel is exception-isolated: one failing channel never breaks a run or
blocks the others.

---

## Setup

```bash
python -m venv venv
venv\Scripts\Activate.ps1          # Windows
pip install -r requirements.txt
copy .env.example .env             # then fill in real values
uvicorn app.main:app --reload
```

Interactive API docs at `http://localhost:8000/docs`.

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The committed suite (`tests/`) is deterministic and needs no API keys or
network: SSRF guard, email injection safety and category selection, SMTP
header-injection defence, JSON parsing, demo helpers. Live integration checks
(real LLM verdicts, real email delivery) are run manually against the
configured providers.

### Environment variables

Names only. Real values go in `.env`, which is gitignored and must never be
committed. See `.env.example` for guidance on each.

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Supabase connection string, needs `?sslmode=require` |
| `GEMINI_API_KEY` | Google AI Studio, free |
| `GROQ_API_KEY` | console.groq.com, free fallback provider |
| `SMTP_USER` / `SMTP_PASSWORD` | Gmail address + 16-char App Password |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com`, 587 (STARTTLS) or 465 (SSL) |
| `OWNER_EMAIL` | Default recipient / demo fallback |
| `WHATSAPP_PHONE` / `WHATSAPP_APIKEY` | Optional CallMeBot channel, off when blank |
| `TICK_SECRET` | Long random string, sent by cron as `X-Tick-Secret` |
| `ACCESS_CODE` | Shared passphrase for the app; blank = open (dev) |
| `DEMO_MODE` | Seed and cycle the demo fleet (default true) |
| `DEMO_CYCLE_MINUTES` | How often the demo target flips open/closed |
| `PUBLIC_BASE_URL` | This backend's public URL, for the demo target link |
| `ALLOWED_ORIGIN` | Frontend origin for CORS |
| `LLM_DAILY_BUDGET` | Gemini calls/day before forcing the Groq fallback |

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness plus a real DB round trip |
| GET | `/stats` | Fleet overview for the dashboard |
| POST | `/watchers` | Commissioner parses a sentence, writes nothing |
| POST | `/watchers/confirm` | Launch the confirmed probe |
| GET | `/watchers` | List the fleet |
| GET | `/watchers/{id}` | Probe detail |
| GET | `/watchers/{id}/runs` | Mission log, newest pass first |
| GET | `/watchers/{id}/transmissions` | Alerts this probe has sent |
| POST | `/watchers/{id}/run-now` | Ping immediately, does not shift the schedule |
| POST | `/watchers/{id}/pause` | Pause |
| POST | `/watchers/{id}/resume` | Resume, re-arms a triggered probe |
| DELETE | `/watchers/{id}` | Retire |
| POST | `/tick` | Cron heartbeat, requires `X-Tick-Secret` |
| GET | `/demo/target` | Public, clearly-labelled demonstration page |
| POST | `/demo/run` | Run one live demonstration on demand |

The watcher endpoints require the `X-Access-Code` header when `ACCESS_CODE` is
set. `/demo/target` is always public (a probe, and a grader, must be able to
read it); `/demo/run` requires the code.

Creating a probe is deliberately two steps so the user sees exactly what the
agent understood before anything is stored.

---

## Decisions, and why

- **Supabase Postgres**, not Neon. Either works; Supabase was chosen. The
  database must live outside the instance because Koyeb's free disk is
  ephemeral and wiped on redeploy.
- **SMTP via a shared Gmail App Password**, not Resend. Resend without a
  verified custom domain only delivers to the account owner's own address, so
  a watcher could never email the address the user typed in. SMTP reaches any
  recipient with no domain and no extra service.
- **psycopg 3**, not psycopg2. Better wheel support on Python 3.14.
- **No user accounts, by design.** One shared access code (`ACCESS_CODE`) gates
  the whole watcher API; the frontend prompts for it once and also asks for the
  user's email for notifications. No signup, to protect the limited free API.
  The code matters because the repo is public and the live URL ends up in it,
  so the URL is effectively public and obscurity is not protection. Even if the
  code leaks, `MAX_ACTIVE_WATCHERS` and the daily LLM budget bound the damage.
- **Honesty of the demo (important).** The always-on fleet watches only real
  sites, so nothing in the background is simulated or passed off as organic
  activity. The one synthetic piece, an appointment-availability target, is
  watched by a single demo probe that runs ONLY when a user presses "Run a
  live demonstration". Both the target page and that probe are labelled as a
  demonstration. So the engine is entirely real; only an explicitly
  user-initiated, clearly-marked target is synthetic. The demonstration alert
  is shown in-app, never emailed.
- **Two-step watcher creation** so the parsed spec is always confirmed by a
  human before an agent goes live.

---

## Gotchas worth remembering

Hard-won during setup. Do not re-learn these the hard way.

- **Gemini model availability shifts.** The 2.5 models now return 404 ("no
  longer available to new users") and 2.0 models return 429 (no free quota).
  Use the 3.x line.
- **`gemini-3.5-flash` returned 503 "experiencing high demand"** for an
  extended stretch. Primary is `gemini-3.6-flash`, with `gemini-flash-latest`
  as a second attempt, then Groq. Free-tier capacity fluctuates hour to hour,
  so **the escalation chain matters more than the exact model choice.**
- **A silent fallback is dangerous.** Every call was quietly being served by
  Groq while Gemini was down, and nothing surfaced it. `llm.py` now logs every
  provider failure and reports which model actually answered via `meta`.
- **Groq is not Grok.** Groq (console.groq.com) is the free Llama inference
  service. xAI's Grok is a different company and is pay-only: a new xAI team
  returns 403 with no credits.
- **Gmail App Passwords require 2-Step Verification** on the account first,
  otherwise the App Passwords page does not appear.
- **Supabase free projects pause after ~1 week idle.** Cron traffic keeps it
  warm; it also wakes on the next query.
- **Deleting a watcher needs the Event cascade**, otherwise Postgres throws a
  foreign key violation.
- **Callsigns come from `max(id)`, not row count**, so retiring a probe never
  causes a later one to reuse an existing callsign.
- **Real-world fetch success is about 70 percent direct, higher with the
  fallback.** Measured 2026-07-22 across 10 varied sites: Wikipedia, Hacker
  News, GitHub releases, python.org, BBC News, Ticketmaster and gov.uk work;
  Reddit, Amazon and Booking.com are JS rendered and out of reach. The
  README should stay honest that JS-heavy storefronts mostly do not work.
- **Pakistani gov and university sites: 10 of 11 usable** (2026-07-23).
  FBR, pakistan.gov.pk, HEC, PPSC jobs, NUST, LUMS, Punjab University, UET,
  COMSATS all read directly. Two need the TLS-verify retry (pakistan.gov.pk,
  HEC have broken cert chains). NADRA blocks bots with a 403 but is rescued
  by the rendering fallback (6k chars of real content). Only NTS stays
  unreadable. PPSC's jobs page is a strong real demo use case.
- **The fetch escalation chain** mirrors the LLM client: direct fetch, then
  a TLS-unverified retry (only on certificate errors, logged), then the
  r.jina.ai rendering proxy (free, keyless, ~20 req/min). The proxy is
  strictly a fallback: it rescued NADRA but returns block pages or nothing
  for Reddit/Amazon/NTS, so it cannot be trusted as a primary.
- **Redirects are followed manually and every hop is re-validated.** An
  auto-following client is an SSRF hole: a public URL that 302s to
  127.0.0.1 or the cloud metadata IP would sail past a create-time check.
  Verified live against httpbin redirect attacks.
- **The byte cap must be enforced while streaming.** Slicing resp.text after
  the download means the whole body was already in memory; a huge page could
  take down the 512 MB Koyeb instance.
- **The demo target page (day 3) must render more than 200 readable chars**,
  or every demo run reports "too little text to judge". Tiny-but-legit pages
  hit the same threshold, and the mission log explains why honestly.
- **Never judge a condition against a scrap of navigation text.** Pages under
  `MIN_USEFUL_CHARS` (200) are reported as unusable with no verdict claimed,
  rather than producing a confident-sounding verdict from menu chrome.
- Failed fetches are recorded as honest error runs and shown in the mission
  log. A probe reporting "target returned 403" is still the agent visibly
  doing its job.

---

## Before this repo goes public

- [ ] **Rotate the Gmail App Password and the Supabase database password.**
      They were shared in plaintext during setup.
- [x] Confirm `.env` is gitignored (verified with a real git test: only
      `.gitignore`, `.env.example` and source get committed).
- [ ] Write the polished public README with screenshots, live URL, and the
      three system prompts printed in full.

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
