from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-only application configuration.

    No endpoint, credential, model name, timeout, or deployment value is
    hard-coded here. Required values must be supplied through backend/.env
    locally or the host's secret/environment configuration in production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str
    app_name: str
    api_v1_prefix: str
    database_url: str
    jwt_secret: SecretStr = Field(min_length=32)
    field_encryption_key: SecretStr
    access_token_minutes: int
    refresh_token_days: int
    allow_public_registration: bool
    cors_origins: str

    ollama_base_url: str
    ollama_model: str
    ollama_timeout: float
    gemini_api_key: SecretStr | None = None
    gemini_model: str
    llm_max_attempts: int

    browser_headless: bool
    browser_timeout_ms: int
    allow_private_targets: bool
    max_concurrency: int
    max_test_cases: int

    use_deepeval: bool
    composite_rule_weight: float
    composite_safety_weight: float
    composite_business_weight: float
    pass_score_threshold: float
    regression_score_drop_threshold: float
    regression_pass_rate_drop_threshold: float

    langfuse_enabled: bool
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str | None = None
    otel_enabled: bool
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str
    langsmith_enabled: bool
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str

    @property
    def cors(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
