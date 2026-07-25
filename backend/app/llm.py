"""Provider-agnostic LLM client: Gemini primary, Groq fallback, JSON out.

All three roles (Commissioner, Watcher, Herald) call complete_json(). The
client enforces a daily Gemini budget tracked in the DB and transparently
falls back to Groq on any Gemini failure (429 rate limits, retired models,
network errors) so the fleet never silently stops.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .config import get_settings

settings = get_settings()
logger = logging.getLogger("argus.llm")


class LLMError(Exception):
    pass


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _safe_parse(raw: str | None) -> dict[str, Any]:
    """Parse model text into JSON, tolerating stray code fences."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.lstrip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        text = text.rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model did not return valid JSON: {text[:200]}") from exc


# ---------------------------------------------------------------------------
# Daily budget (free Gemini quotas are small and undocumented)
# ---------------------------------------------------------------------------
# These deliberately use their own short-lived session. Sharing the caller's
# session would commit the caller's half-finished work (for example a partially
# processed watcher run) every time a budget row is touched.
def _within_budget() -> bool:
    from .db import SessionLocal
    from .models import BudgetCounter

    with SessionLocal() as s:
        row = s.get(BudgetCounter, _today())
        return (row.gemini_calls if row else 0) < settings.llm_daily_budget


def _record(provider: str) -> None:
    from .db import SessionLocal
    from .models import BudgetCounter

    with SessionLocal() as s:
        row = s.get(BudgetCounter, _today())
        if row is None:
            row = BudgetCounter(day=_today(), gemini_calls=0, groq_calls=0)
            s.add(row)
        if provider == "gemini":
            row.gemini_calls += 1
        else:
            row.groq_calls += 1
        s.commit()


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
def _call_gemini(
    model: str, system: str, user: str, schema: dict | None
) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=0.2,
    )
    if schema:
        config.response_schema = schema
    resp = client.models.generate_content(model=model, contents=user, config=config)
    return _safe_parse(resp.text)


def _call_groq(system: str, user: str) -> dict[str, Any]:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return _safe_parse(resp.choices[0].message.content)


def complete_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
    schema: dict | None = None,
    meta: dict | None = None,
) -> dict[str, Any]:
    """Return a parsed JSON object from the model.

    Escalation order: the requested Gemini model, then a backup Gemini model
    (free-tier capacity moves around and 503s are common), then Groq. Every
    failure is logged, because a silent fallback means we would never notice
    that the primary provider stopped working.

    Pass a dict as `meta` to learn which provider/model actually answered.
    """
    primary = model or settings.gemini_model_commissioner
    errors: list[str] = []

    if settings.gemini_api_key and _within_budget():
        candidates = [primary]
        if settings.gemini_model_backup and settings.gemini_model_backup != primary:
            candidates.append(settings.gemini_model_backup)
        for candidate in candidates:
            try:
                out = _call_gemini(candidate, system, user, schema)
                _record("gemini")
                if meta is not None:
                    meta.update(provider="gemini", model=candidate)
                return out
            except Exception as exc:
                logger.warning("Gemini model %s failed: %s", candidate, exc)
                errors.append(f"gemini/{candidate}: {type(exc).__name__}: {exc}")

    if settings.groq_api_key:
        try:
            out = _call_groq(system, user)
            _record("groq")
            if meta is not None:
                meta.update(provider="groq", model=settings.groq_model)
            logger.warning(
                "Served by Groq fallback (%s) after Gemini failed", settings.groq_model
            )
            return out
        except Exception as exc:
            logger.error("Groq fallback failed: %s", exc)
            errors.append(f"groq: {type(exc).__name__}: {exc}")

    raise LLMError("all providers failed -> " + " | ".join(errors or ["no keys set"]))
