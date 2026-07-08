"""Central configuration, driven entirely by environment variables.

Keeping every piece of infra config in env vars means the dev setup (native Ollama +
local Qdrant) and the demo setup (Dockerized Ollama + Qdrant) differ only by values,
never by code (spec §15; brief "dev vs finishing split"). Nothing here is hardcoded.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Local LLM runtime (Ollama) ---
    ollama_host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    llm_model: str = Field(default="qwen3:4b-instruct", alias="LLM_MODEL")
    llm_quantization: str = Field(default="", alias="LLM_QUANTIZATION")

    # --- Embeddings ---
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL"
    )

    # --- Vector store (Qdrant) ---
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_project_collection: str = Field(
        default="project_knowledge", alias="QDRANT_PROJECT_COLLECTION"
    )
    qdrant_org_collection: str = Field(
        default="organizational_knowledge", alias="QDRANT_ORG_COLLECTION"
    )

    # --- Storage ---
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    sqlite_url: str = Field(
        default="sqlite:///./data/app.db", alias="SQLITE_URL"
    )

    @property
    def documents_dir(self) -> Path:
        """Per spec §20.2: filesystem access restricted to the project data directory."""
        return self.data_dir / "documents"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so config is read once per process."""
    settings = Settings()
    # Ensure local data directories exist in dev; harmless if already present.
    os.makedirs(settings.documents_dir, exist_ok=True)
    return settings
