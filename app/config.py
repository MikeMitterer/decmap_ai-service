from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_url: str = "postgresql://decisionmap:decisionmap@localhost:5432/decisionmap"
    embedding_provider: str = "openai"
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    similarity_threshold: float = 0.85
    duplicate_threshold: float = 0.92
    clustering_interval: int = 360
    bot_submit_min_seconds: int = 10
    bot_session_max_hourly: int = 10
    bot_ip_max_sessions: int = 5
    app_version: str = "0.1.0"
    webhook_secret: str = ""
    # Rate limit for POST /similarity — format: "<count>/<period>" e.g. "10/minute"
    similarity_rate_limit: str = "10/minute"
    # Comma-separated list of allowed CORS origins.
    # Example: "https://app.example.com,https://admin.example.com"
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
