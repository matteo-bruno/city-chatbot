"""Configuration, entirely from environment variables.

Keeping every knob in the environment (and nothing in code) is what makes the
service portable: the same image runs a different city, a different provider,
a different model or a different geocoder with no edits. `.env.example`
documents the full set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROVIDER = "gemini"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_any(names: tuple[str, ...], default: str = "") -> str:
    """First of several env vars that is set, for provider key aliases."""
    for name in names:
        value = _env(name)
        if value:
            return value
    return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_opt_int(name: str) -> int | None:
    raw = _env(name)
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _env_opt_float(name: str) -> float | None:
    raw = _env(name)
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


@dataclass
class Settings:
    # --- provider and model -------------------------------------------------
    provider: str = DEFAULT_PROVIDER
    #: empty means "the provider's own default model"
    model: str = ""
    max_tokens: int = 4096
    max_tool_rounds: int = 8

    # --- provider credentials -----------------------------------------------
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    anthropic_api_key: str = ""

    # --- Gemini-specific ----------------------------------------------------
    temperature: float | None = None
    thinking_budget: int | None = None

    # --- Anthropic-specific -------------------------------------------------
    effort: str = "medium"  # low | medium | high | xhigh | max
    refusal_fallback: bool = True

    # --- data ----------------------------------------------------------------
    data_dir: Path = field(default_factory=lambda: Path("data"))
    knowledge_dir: Path = field(default_factory=lambda: Path("knowledge"))
    city: str = ""

    # --- optional online search ---------------------------------------------
    web_search: bool = False
    web_search_max_uses: int = 4
    web_search_allowed_domains: list[str] = field(default_factory=list)

    # --- optional live geocoding --------------------------------------------
    geocoder: str = "none"  # none | nominatim
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    geocoder_user_agent: str = "city-chatbot/0.1"
    geocoder_email: str = ""

    # --- server --------------------------------------------------------------
    allow_origins: list[str] = field(default_factory=lambda: ["*"])
    max_sessions: int = 200
    max_history_messages: int = 40

    @classmethod
    def from_env(cls) -> Settings:
        domains = [d.strip() for d in _env("CITYCHAT_WEB_SEARCH_DOMAINS").split(",") if d.strip()]
        origins = [o.strip() for o in _env("CITYCHAT_ALLOW_ORIGINS", "*").split(",") if o.strip()]
        return cls(
            provider=_env("CITYCHAT_PROVIDER", DEFAULT_PROVIDER).lower(),
            model=_env("CITYCHAT_MODEL"),
            max_tokens=_env_int("CITYCHAT_MAX_TOKENS", 4096),
            max_tool_rounds=_env_int("CITYCHAT_MAX_TOOL_ROUNDS", 8),
            gemini_api_key=_env_any(("GEMINI_API_KEY", "GOOGLE_API_KEY")),
            gemini_base_url=_env(
                "CITYCHAT_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
            ),
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            temperature=_env_opt_float("CITYCHAT_TEMPERATURE"),
            thinking_budget=_env_opt_int("CITYCHAT_THINKING_BUDGET"),
            effort=_env("CITYCHAT_EFFORT", "medium"),
            refusal_fallback=_env_bool("CITYCHAT_REFUSAL_FALLBACK", True),
            data_dir=Path(_env("CITYCHAT_DATA_DIR", "data")),
            knowledge_dir=Path(_env("CITYCHAT_KNOWLEDGE_DIR", "knowledge")),
            city=_env("CITYCHAT_CITY"),
            web_search=_env_bool("CITYCHAT_WEB_SEARCH", False),
            web_search_max_uses=_env_int("CITYCHAT_WEB_SEARCH_MAX_USES", 4),
            web_search_allowed_domains=domains,
            geocoder=_env("CITYCHAT_GEOCODER", "none").lower(),
            nominatim_url=_env("CITYCHAT_NOMINATIM_URL", "https://nominatim.openstreetmap.org"),
            geocoder_user_agent=_env("CITYCHAT_GEOCODER_USER_AGENT", "city-chatbot/0.1"),
            geocoder_email=_env("CITYCHAT_GEOCODER_EMAIL"),
            allow_origins=origins or ["*"],
            max_sessions=_env_int("CITYCHAT_MAX_SESSIONS", 200),
            max_history_messages=_env_int("CITYCHAT_MAX_HISTORY_MESSAGES", 40),
        )

    @property
    def cities_dir(self) -> Path:
        return self.data_dir / "cities"

    @property
    def places_dir(self) -> Path:
        return self.data_dir / "places"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def api_key_for_provider(self) -> str:
        return {
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
        }.get(self.provider, "")
