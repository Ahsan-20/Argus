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

**Day 1 of 6 complete (2026-07-22). Audited, 17/17 automated checks passing.**

Working:
- FastAPI app on Supabase Postgres, tables auto-create on startup
- LLM client with escalation: Gemini primary, backup Gemini model, then Groq
- Daily LLM budget counter tracked in the database
- **The Commissioner**: plain English becomes a structured watcher spec
- Watcher management: create, confirm, list, get, pause, resume, retire
- Secured `/tick` heartbeat with atomic claiming of due watchers
- SSRF guard enforced at watcher creation, not just at fetch time

Next (day 2): the fetcher against real pages, the Watcher role that judges each
pass, the tick run loop, and a run-now endpoint for instant demos.

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
| `app/routers/watchers.py` | Commissioner flow and fleet management |

### The three AI roles

All prompts live in `app/prompts.py` and are printed in full in the final
README (a grading requirement). Never inline a prompt anywhere else.

1. **The Commissioner** turns a sentence into a testable watcher spec, or refuses.
2. **The Watcher** judges one fetch against the condition and returns a verdict
   with confidence, evidence and reasoning.
3. **The Herald** writes the alert email once a probe triggers.

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
- Some sites block datacenter IPs or need JavaScript. Failed fetches are
  recorded honestly as error runs rather than hidden.

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
