"""
Provider factory (consider renaming this file to provider_factory.py for clarity).

This is the ONLY place that maps AI_PROVIDER setting values to concrete
AIProvider classes. To add a new provider:
  1. Create app/<name>_provider.py implementing AIProvider
  2. Add one line to PROVIDER_REGISTRY below
  3. Set AI_PROVIDER=<name> in .env
No other file in the app changes.
"""
from __future__ import annotations

from app.config import get_settings
from app.providers_base import AIProvider
from app.claude_provider import ClaudeProvider
from app.google_provider import GoogleProvider
from app.groq_provider import GroqProvider
from app.openrouter_provider import OpenRouterProvider

PROVIDER_REGISTRY: dict[str, type[AIProvider]] = {
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "google": GoogleProvider,
    "claude": ClaudeProvider,
}


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    requested = settings.ai_provider.lower()

    if requested == "auto":
        return _get_available_provider()

    provider_cls = PROVIDER_REGISTRY.get(requested)
    if provider_cls is None:
        raise ValueError(
            f"Unknown AI_PROVIDER '{settings.ai_provider}'. "
            f"Available providers: {', '.join(PROVIDER_REGISTRY)}"
        )
    return provider_cls()


def _get_available_provider() -> AIProvider:
    """Return the first provider for which a key is configured."""
    settings = get_settings()
    if settings.openrouter_api_key:
        return OpenRouterProvider()
    if settings.google_api_key:
        return GoogleProvider()
    if settings.groq_api_key:
        return GroqProvider()
    # Last resort: GroqProvider will raise a clear error at call time.
    return GroqProvider()


def get_fallback_provider(primary_provider: AIProvider) -> AIProvider:
    """Return a different provider than primary_provider, if one is configured."""
    settings = get_settings()
    candidates: list[str] = []
    if settings.openrouter_api_key:
        candidates.append("openrouter")
    if settings.google_api_key:
        candidates.append("google")
    if settings.groq_api_key:
        candidates.append("groq")

    for name in candidates:
        cls = PROVIDER_REGISTRY.get(name)
        if cls is not None and not isinstance(primary_provider, cls):
            return cls()

    return primary_provider  # no alternative available