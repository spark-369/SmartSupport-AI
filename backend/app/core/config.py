"""Typed application settings loaded from environment / `.env` (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration. Every value can be overridden with a
    ``SMARTSUPPORT_``-prefixed environment variable."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SMARTSUPPORT_",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "SmartSupport AI"
    app_version: str = "1.0.0"
    environment: Literal["dev", "test", "prod"] = "dev"
    debug: bool = True
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:mysecretpassword@localhost:5432/smartsupport"
    sync_database_url: str = "postgresql+psycopg2://postgres:mysecretpassword@localhost:5432/smartsupport"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # --- Auth / JWT ---
    jwt_secret: str = "dev_9f2c7a1e5b8d4f6a0c3e7b1d9a8f5c2e"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "ss_refresh_token"
    cookie_secure: bool = False  # set True behind HTTPS in production

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Ollama / models ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 120.0
    embedding_model: str = "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0"
    llm_model: str = "hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M"
    llm_temperature: float = 0.2
    llm_num_ctx: int = 8192
    answer_max_tokens: int = 1024

    # --- RAG tuning ---
    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.20
    chunk_size: int = 1000
    chunk_overlap: int = 150
    embed_batch_size: int = 32
    max_embed_chars: int = 6000
    rag_history_messages: int = 6

    # --- Storage ---
    upload_dir: Path = Path("data/uploads")
    max_upload_mb: int = 20
    allowed_upload_extensions: set[str] = {".pdf", ".md", ".markdown", ".txt", ".docx"}

    # --- Rate limiting (Redis sliding window) ---
    rate_limit_register_per_minute: int = 20
    rate_limit_login_per_minute: int = 10
    rate_limit_chat_per_minute: int = 20
    rate_limit_upload_per_hour: int = 30
    rate_limit_search_per_minute: int = 30
    rate_limit_triage_per_minute: int = 20

    # --- Cache TTLs (seconds) ---
    embedding_cache_ttl: int = 7 * 24 * 3600
    retrieval_index_cache_ttl: int = 3600

    # --- Seeding ---
    seed_admin_email: str = "admin@smartsupport.io"
    seed_admin_password: str = "Admin12345!"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend_url(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()
