"""
Provider factory.

This is the ONLY place that knows which concrete AIProvider class maps to
the AI_PROVIDER setting. To add a new provider:
  1. Create app/services/providers/<name>_provider.py implementing AIProvider
  2. Add one line to PROVIDER_REGISTRY below
  3. Set AI_PROVIDER=<name> in .env
No other file in the app changes.
"""
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
    # "gemini": GeminiProvider,        # implement and register when needed
    # "together": TogetherProvider,
    # "cerebras": CerebrasProvider,
    # "openai": OpenAIProvider,
}


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    requested_provider = settings.ai_provider.lower()

    if requested_provider == "auto":
        return _get_available_provider()

    provider_cls = PROVIDER_REGISTRY.get(requested_provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown AI_PROVIDER '{settings.ai_provider}'. "
            f"Available providers: {', '.join(PROVIDER_REGISTRY)}"
        )
    return provider_cls()


def _get_available_provider() -> AIProvider:
    settings = get_settings()
    if settings.openrouter_api_key:
        return PROVIDER_REGISTRY["openrouter"]()
    if settings.google_api_key:
        return PROVIDER_REGISTRY["google"]()
    if settings.groq_api_key:
        return PROVIDER_REGISTRY["groq"]()
    return GroqProvider()


def get_fallback_provider(primary_provider: AIProvider) -> AIProvider:
    settings = get_settings()
    candidates = []
    if settings.openrouter_api_key:
        candidates.append("openrouter")
    if settings.google_api_key:
        candidates.append("google")
    if settings.groq_api_key:
        candidates.append("groq")

    for provider_name in candidates:
        provider_cls = PROVIDER_REGISTRY.get(provider_name)
        if provider_cls is None:
            continue
        if not isinstance(primary_provider, provider_cls):
            return provider_cls()
    return primary_provider
