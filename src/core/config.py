"""Application configuration and explicit runtime readiness checks.

Configuration is intentionally loadable without secrets so that unit tests,
schema migrations and the liveness endpoint do not require production access.
Processes that contact Telegram, a database, an M2M API or an LLM must call
``validate_runtime`` before doing so.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# TODO(MAX): replace the values below with secrets supplied by the production
# secret manager once the infrastructure access listed in the technical task is
# available. Never use these empty defaults to make an external request.


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Configuration
    telegram_bot_token: str = ""
    telegram_approval_chat_id: int | None = None

    # Database Configuration
    database_url: str = "sqlite+aiosqlite:///./bot_local.db"
    database_echo: bool = False

    # M2M API Configuration
    m2m_api_key: str = ""
    fuckhr_api_base_url: str = "http://localhost:8001"
    jobs_api_base_url: str = "http://localhost:8002"
    use_mocks: bool = False

    # LLM Configuration
    llm_provider_key: str = ""
    llm_provider: str = "openai"
    llm_model: str = "gpt-4-turbo"
    llm_base_url: str | None = None

    # Application Configuration
    log_level: str = "INFO"
    debug: bool = False
    app_name: str = "QuickOffer Support Bot"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=list)
    internal_webhook_token: str = ""

    # Staff Approval Configuration
    staff_allowlist_json: str = "{}"
    refund_decision_timeout_minutes: int = 60
    yookassa_dashboard_url: str = "https://dashboard.yookassa.ru"

    # RAG Configuration (Mode B)
    rag_kb_base_url: str = "http://localhost:8003"
    rag_max_retrieval_count: int = 5
    rag_confidence_threshold: float = 0.7

    # Handoff Configuration
    handoff_timeout_minutes: int = 120
    handoff_facts_retention_days: int = 30

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    def validate_runtime(self, *capabilities: str) -> None:
        """Fail closed when a process lacks credentials it is about to use."""
        required: dict[str, tuple[str, ...]] = {
            "bot": ("telegram_bot_token", "telegram_approval_chat_id"),
            "m2m": ("m2m_api_key",),
            "llm": ("llm_provider_key",),
            "webhook": ("internal_webhook_token",),
        }
        missing: list[str] = []
        for capability in capabilities:
            for name in required.get(capability, ()):
                if not getattr(self, name):
                    missing.append(name.upper())
        if missing:
            raise RuntimeError(
                "Missing required runtime configuration: "
                + ", ".join(sorted(set(missing)))
            )


settings = Settings()
