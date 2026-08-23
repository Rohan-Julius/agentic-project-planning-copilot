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
    # Day 25: defaults to "cpu", not sentence-transformers' own auto-detected GPU (mps on
    # Apple Silicon). Live-observed: this embedding model and Ollama's own loaded LLM sharing
    # one GPU on the same machine produced both "Insufficient Memory
    # kIOGPUCommandBufferCallbackErrorOutOfMemory" noise during embedding calls AND, on one
    # live run, an outright HTTP 500 from Ollama's own /api/generate shortly after embedding
    # activity -- plausibly the same GPU-contention class, not confirmed as the sole cause but
    # a real, unnecessary risk either way. bge-small (33M params) is fast enough on CPU that
    # this isn't a meaningful latency cost, and it fully removes any GPU contention with
    # Ollama's LLM, which is where GPU acceleration actually matters. Override via
    # EMBEDDING_DEVICE if your deployment doesn't share a GPU between the two services.
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")

    # --- Chunking (spec §6.3, DESIGN.md §5.1) ---
    chunk_token_limit: int = Field(default=512, alias="CHUNK_TOKEN_LIMIT")
    chunk_overlap_ratio: float = Field(default=0.15, alias="CHUNK_OVERLAP_RATIO")

    # --- Vector store (Qdrant) ---
    qdrant_url: str | None = Field(
        default=None,
        alias="QDRANT_URL",
        description=(
            "Qdrant server URL. Leave unset (default) to use an embedded, file-backed "
            "Qdrant store under DATA_DIR/qdrant_local — no server process or Docker "
            "required. Set to a URL (e.g. http://localhost:6333) to use a running "
            "Qdrant server instead."
        ),
    )
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

    # --- Frontend (CORS) ---
    cors_origins: str = Field(
        default="http://localhost:5173", alias="CORS_ORIGINS"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def documents_dir(self) -> Path:
        """Per spec §20.2: filesystem access restricted to the project data directory."""
        return self.data_dir / "documents"

    @property
    def exports_dir(self) -> Path:
        """Per spec §20.2: exports are written here, never into documents_dir — an export
        must never overwrite a source document.
        """
        return self.data_dir / "exports"

    @property
    def qdrant_local_path(self) -> Path:
        """Embedded Qdrant storage directory, used when QDRANT_URL is unset (no Docker
        needed). qdrant-client locks this directory to one process at a time.
        """
        return self.data_dir / "qdrant_local"

    @property
    def checkpoint_db_path(self) -> Path:
        """LangGraph's SQLite-backed checkpointer (DESIGN.md §7.5) — separate from the
        application's own `sqlite_url` DB so graph checkpoints and application rows can be
        backed up/rotated independently.
        """
        return self.data_dir / "checkpoints.sqlite"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so config is read once per process."""
    settings = Settings()
    # Ensure local data directories exist in dev; harmless if already present.
    os.makedirs(settings.documents_dir, exist_ok=True)
    os.makedirs(settings.exports_dir, exist_ok=True)
    return settings
