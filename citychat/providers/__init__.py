"""Provider registry.

`CITYCHAT_PROVIDER` picks one. Adding a third means writing a `Provider`
subclass and adding one line to `BUILDERS`.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings
from .anthropic import DEFAULT_MODEL as ANTHROPIC_DEFAULT_MODEL
from .anthropic import AnthropicProvider
from .base import (
    ModelTurn,
    Provider,
    ProviderError,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from .gemini import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from .gemini import GeminiProvider

__all__ = [
    "ANTHROPIC_DEFAULT_MODEL",
    "GEMINI_DEFAULT_MODEL",
    "AnthropicProvider",
    "GeminiProvider",
    "ModelTurn",
    "Provider",
    "ProviderError",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "DEFAULT_MODELS",
    "PROVIDERS",
    "build_provider",
]

DEFAULT_MODELS = {
    "gemini": GEMINI_DEFAULT_MODEL,
    "anthropic": ANTHROPIC_DEFAULT_MODEL,
}

PROVIDERS = tuple(DEFAULT_MODELS)


def _build_gemini(settings: Settings, system_prompt: str, tools: list[ToolSpec], **kwargs: Any):
    return GeminiProvider(
        model=settings.model or GEMINI_DEFAULT_MODEL,
        system_prompt=system_prompt,
        tools=tools,
        api_key=settings.gemini_api_key,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        thinking_budget=settings.thinking_budget,
        base_url=settings.gemini_base_url,
        web_search=settings.web_search,
        **kwargs,
    )


def _build_anthropic(settings: Settings, system_prompt: str, tools: list[ToolSpec], **kwargs: Any):
    return AnthropicProvider(
        model=settings.model or ANTHROPIC_DEFAULT_MODEL,
        system_prompt=system_prompt,
        tools=tools,
        api_key=settings.anthropic_api_key,
        max_tokens=settings.max_tokens,
        effort=settings.effort,
        refusal_fallback=settings.refusal_fallback,
        web_search=settings.web_search,
        web_search_max_uses=settings.web_search_max_uses,
        web_search_allowed_domains=settings.web_search_allowed_domains,
        **kwargs,
    )


BUILDERS = {"gemini": _build_gemini, "anthropic": _build_anthropic}


def build_provider(
    settings: Settings, system_prompt: str, tools: list[ToolSpec], **kwargs: Any
) -> Provider:
    builder = BUILDERS.get(settings.provider)
    if builder is None:
        raise RuntimeError(
            f"unknown CITYCHAT_PROVIDER {settings.provider!r}; available: {', '.join(PROVIDERS)}"
        )
    return builder(settings, system_prompt, tools, **kwargs)
