"""Application settings, loaded from environment / .env.

Every secret and tunable lives here so nothing is hardcoded elsewhere.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Core ----
    app_env: str = "development"
    database_url: str = ""  # Supabase Postgres connection string
    # Frontend origin(s) allowed to call the API. Comma separated, because
    # Vercel serves preview deployments on their own hostnames alongside the
    # production one and a single value locks those out.
    allowed_origin: str = "http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origin.split(",") if o.strip()]

    # ---- LLM providers ----
    gemini_api_key: str = ""
    groq_api_key: str = ""
    # Verified live against this key on 2026-07-22: the 2.5 and 2.0 models are
    # retired or quota-locked for new accounts (404 / 429). The 3.x line works
    # with JSON schema output. The Watcher is the hot path so it runs on
    # Flash-Lite for quota headroom; Commissioner and Herald are rare calls and
    # use full Flash for better judgement.
    # Re-verified 2026-07-22: gemini-3.5-flash was returning 503 "high demand",
    # so the primary is 3.6-flash. Free-tier capacity moves around, hence the
    # secondary Gemini model tried before dropping to Groq.
    gemini_model_commissioner: str = "gemini-3.6-flash"
    gemini_model_watcher: str = "gemini-3.5-flash-lite"
    gemini_model_herald: str = "gemini-3.6-flash"
    gemini_model_backup: str = "gemini-flash-latest"
    groq_model: str = "llama-3.3-70b-versatile"
    llm_daily_budget: int = 200  # max Gemini calls/day before Groq fallback

    # ---- Email (SMTP, e.g. Gmail app password) ----
    # A single shared sender account delivers alerts to whatever address the
    # user set on the watcher. Gmail: use an App Password, not your login pw.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465  # SSL
    smtp_user: str = ""  # the sender email address
    smtp_password: str = ""  # the App Password
    smtp_from_name: str = "Argus Mission Control"
    # Optional default recipient (demo fleet / fallback when a watcher has none).
    owner_email: str = ""

    # Optional HTTP mail transport. Hosting providers commonly block outbound
    # SMTP, and a blocked port hangs rather than failing, so a request that
    # sends mail never returns. An HTTP API leaves on 443 like anything else.
    # Set this and mail goes that way; leave it blank and SMTP is used.
    brevo_api_key: str = ""

    # ---- WhatsApp channel (optional second channel, via CallMeBot) ----
    # Free, no signup: message the CallMeBot number once to get an api key
    # bound to your number. Leave blank to keep the channel off. Alerts still
    # go by email; WhatsApp is added on top when both fields are set.
    whatsapp_phone: str = ""  # recipient in international form, e.g. +9231...
    whatsapp_apikey: str = ""

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_phone and self.whatsapp_apikey)

    # ---- Being a good guest on other people's servers ----
    # Argus identifies itself rather than impersonating a browser. The
    # conventional "Mozilla/5.0 (compatible; Name/version; +url)" shape is what
    # Googlebot and friends use: honest about being software, and reachable if
    # an operator wants us to stop. Spoofing Chrome would be more likely to get
    # through a few doors, but it is deceptive, it removes the site owner's
    # ability to contact us, and it is the behaviour that pushes sites toward
    # ever more aggressive blocking.
    user_agent: str = ""  # blank builds the default from public_base_url
    respect_robots: bool = True  # obey robots.txt, including Crawl-delay
    crawl_delay_seconds: float = 2.0  # floor between hits on one host
    max_crawl_delay_seconds: float = 30.0  # cap on a hostile Crawl-delay
    # A page that has not changed can be answered from the previous verdict
    # instead of being read again, but a condition about timing ("closes within
    # a week") can turn true while the page sits still, so a full re-read is
    # forced this often regardless.
    full_recheck_hours: int = 6

    # ---- Scheduler / limits ----
    # Argus keeps its own time. The loop lives in the process and checks the
    # database for due watchers, so a watcher runs within about a minute of
    # when it was scheduled rather than whenever an outside cron got round to
    # it. Turn it off to go back to being driven purely by POST /tick.
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60
    tick_secret: str = ""  # shared secret the cron sends in a header
    max_runs_per_tick: int = 5
    max_active_watchers: int = 25  # facility-wide cap
    max_watchers_per_user: int = 5  # per operator email, any status

    # ---- Accounts ----
    # Signs session tokens and password reset links. Changing it logs everyone
    # out and invalidates outstanding reset links, which is exactly what you
    # want if it ever leaks. Must be set in production; a blank value in
    # development falls back to a per boot random value, so tokens simply do
    # not survive a restart rather than being signed with a guessable key.
    secret_key: str = ""
    session_days: int = 30  # how long a login lasts before re-entry
    # An unverified account still works for this long, so someone can try the
    # app the moment they sign up. After it, verification is required.
    verify_grace_hours: int = 24
    reset_token_hours: int = 1  # password reset links are short lived
    # Optional first account, created once on boot so the watchers that
    # predate accounts have an owner who can sign in and claim them. Leave the
    # password blank and nothing is created.
    seed_account_email: str = ""
    seed_account_password: str = ""
    # Where the emailed verify / reset links point. The frontend, not the API.
    frontend_base_url: str = "http://localhost:5173"

    # ---- Demo ----
    # Legacy shared passphrase, retired in favour of real accounts. Kept so an
    # old deployment's env does not fail to parse; it is no longer read.
    access_code: str = ""
    # Seed and keep a demo fleet alive so the deployed site looks active.
    demo_mode: bool = True
    demo_cycle_minutes: int = 20  # how often the demo target flips open/closed
    # Public base URL of THIS backend, used to display the demo target link.
    public_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
