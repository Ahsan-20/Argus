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
    allowed_origin: str = "http://localhost:5173"  # Vercel origin in prod

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

    # ---- WhatsApp channel (optional second channel, via CallMeBot) ----
    # Free, no signup: message the CallMeBot number once to get an api key
    # bound to your number. Leave blank to keep the channel off. Alerts still
    # go by email; WhatsApp is added on top when both fields are set.
    whatsapp_phone: str = ""  # recipient in international form, e.g. +9231...
    whatsapp_apikey: str = ""

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_phone and self.whatsapp_apikey)

    # ---- Scheduler / limits ----
    tick_secret: str = ""  # shared secret the cron sends in a header
    max_runs_per_tick: int = 5
    max_active_watchers: int = 25

    # ---- Access + demo ----
    # Shared passphrase the frontend sends as X-Access-Code. Empty = open (dev).
    access_code: str = ""
    # Seed and keep a demo fleet alive so the deployed site looks active.
    demo_mode: bool = True
    demo_cycle_minutes: int = 20  # how often the demo target flips open/closed
    # Public base URL of THIS backend, used to display the demo target link.
    public_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
