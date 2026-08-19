"""Application configuration using Pydantic settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Configuration
    telegram_bot_token: str
    telegram_approval_chat_id: int

    # Database Configuration
    database_url: str
    database_echo: bool = False

    # M2M API Configuration
    m2m_api_key: str
    fuckhr_api_base_url: str = "http://localhost:8001"
    jobs_api_base_url: str = "http://localhost:8002"

    # LLM Configuration
    llm_provider_key: str
    llm_provider: str = "openai"
    llm_model: str = "gpt-4-turbo"

    # Application Configuration
    log_level: str = "INFO"
    debug: bool = False
    app_name: str = "QuickOffer Support Bot"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

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

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
