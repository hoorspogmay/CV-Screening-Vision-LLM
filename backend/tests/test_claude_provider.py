import app.config as config
from app.ai_provider import get_ai_provider
from app.claude_provider import ClaudeProvider


def test_claude_provider_is_registered_and_reads_key(monkeypatch) -> None:
    config.get_settings.cache_clear()
    monkeypatch.setenv("AI_PROVIDER", "claude")
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    config.get_settings.cache_clear()

    provider = get_ai_provider()

    assert isinstance(provider, ClaudeProvider)
    assert provider._api_key == "test-key"
