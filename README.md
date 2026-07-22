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

**Day 3 in progress (2026-07-23). End-to-end alerts now work.**

Working:
- FastAPI app on Supabase Postgres, tables auto-create on startup
- LLM client with escalation: Gemini primary, backup Gemini model, then Groq
- Daily LLM budget counter tracked in the database
- **The Commissioner**: plain English becomes a structured watcher spec
- **The Watcher**: fetches a live page and returns a verdict with confidence,
  a quoted evidence line, and mission-log reasoning
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

Next (day 3): the self-hosted demo target page, then deploy to Koyeb + cron.

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
| `app/routers/watchers.py` | Commissioner flow and fleet management |

### The three AI roles

All prompts live in `app/prompts.py` and are printed in full in the final
README (a grading requirement). Never inline a prompt anywhere else.

1. **The Commissioner** turns a sentence into a testable watcher spec, or refuses.
2. **The Watcher** judges one fetch against the condition and returns a verdict
   with confidence, evidence and reasoning.
3. **The Herald** writes the alert (subject + body) once a probe triggers. A
   deterministic template is used if the model call fails, so an alert is
   never lost to an LLM hiccup.

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
| `ALLOWED_ORIGIN` | Frontend origin for CORS |
| `LLM_DAILY_BUDGET` | Gemini calls/day before forcing the Groq fallback |

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
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
- **No user accounts, by design.** Single-user demo app. Protected instead by
  the `/tick` shared secret, a global cap on active watchers, and validation
  on every user-supplied URL.
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
survives an LLM failure. Next: the demo target page, then Koyeb deploy + cron.
