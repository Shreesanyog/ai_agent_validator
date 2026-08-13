"""Centralized application configuration.

All configuration is read from environment variables (optionally loaded
from a .env file). See .env.example at the project root for the full list
of supported variables and their defaults.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./avaas.db"

    # LLM provider: mock | ollama | gemini
    llm_provider: str = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # Execution
    request_timeout_seconds: float = 15.0
    max_concurrency: int = 8

    # Evaluation / scoring
    pass_score_threshold: float = 70.0
    composite_rule_weight: float = 0.6
    composite_llm_weight: float = 0.4
    llm_judge_fallback_heuristic: bool = True

    # Regression gate
    regression_score_drop_threshold: float = 10.0
    regression_pass_rate_drop_threshold: float = 0.1

    # Demo agent
    demo_agent_port: int = 9000
    demo_agent_bug_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton for the process)."""
    return Settings()
