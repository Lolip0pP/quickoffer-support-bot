from src.core.config import Settings


def test_local_configuration_allows_telegram_free_demo():
    settings = Settings(_env_file=None)
    assert settings.telegram_bot_token == ""
    assert settings.llm_provider == "local"
    assert settings.llm_base_url == "http://localhost:4000/v1"


def test_openrouter_configuration_is_accepted():
    settings = Settings(
        _env_file=None,
        llm_provider="openrouter",
        llm_base_url="https://openrouter.ai/api/v1",
    )
    assert settings.llm_provider == "openrouter"
