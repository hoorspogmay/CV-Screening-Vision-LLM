import app.config as config
from app.services.providers.openrouter_provider import OpenRouterProvider


def test_openrouter_provider_splits_multiple_api_keys(monkeypatch) -> None:
    config.get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "key-one, key-two")
    config.get_settings.cache_clear()

    provider = OpenRouterProvider()

    assert provider._api_keys == ["key-one", "key-two"]
