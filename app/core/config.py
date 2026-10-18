"""Typed settings loaded from environment variables or an optional local .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings; external services remain optional in the scaffold."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str | None = None
    development_database_name: str | None = None
    development_database_role: str | None = None
    development_database_schema: str | None = None
    llm_provider: str | None = None
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "LLM_API_KEY")
    )
    gemini_api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    llm_model: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_output_tokens: int = 800
    embedding_model: str | None = None
    semantic_model_cache_dir: str | None = None
    semantic_embedding_batch_size: int = 16
    reranker_model: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""

    return Settings()
