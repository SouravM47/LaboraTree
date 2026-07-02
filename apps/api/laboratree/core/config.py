"""Application settings, loaded from environment / .env.

Every value has a safe development default, so the app boots even with a bare .env.
LLM settings support Azure OpenAI (via the OpenAI-compatible v1 route) or plain OpenAI.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = .../apps/api/laboratree/core/config.py -> parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "development"
    api_port: int = 8000
    secret_key: str = "dev-secret-change-me-to-a-long-random-value-32b+"
    log_level: str = "INFO"

    # --- LLM provider: "azure" | "openai" ---
    llm_provider: str = "azure"

    # Azure OpenAI (OpenAI-compatible v1 route works for gpt-5.x and serverless models)
    azure_openai_api_key: str = ""
    azure_openai_v1_endpoint: str = ""
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_deployment_name: str = "gpt-5.4"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_temperature: float = 0.0
    generation_model: str = ""
    reasoning_model: str = ""

    # Plain OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-5.1"
    openai_embedding_model: str = "text-embedding-3-small"

    # --- Postgres ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "laboratree"
    postgres_password: str = "laboratree"
    postgres_db: str = "laboratree"

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "laboratree"

    # --- MongoDB ---
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_user: str = "laboratree"
    mongo_password: str = "laboratree"
    mongo_db: str = "laboratree"

    # --- Blob storage ---
    blob_backend: str = "local"
    blob_local_root: str = ""

    # ---------- derived ----------
    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_sync_dsn(self) -> str:
        """Sync DSN for Alembic migrations."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def mongo_uri(self) -> str:
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/?authSource=admin"
        )

    @property
    def blob_root(self) -> Path:
        root = Path(self.blob_local_root) if self.blob_local_root else (REPO_ROOT / "data" / "blobs")
        return root


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
