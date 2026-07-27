"""Settings tests — Qdrant URL is optional; unset means embedded/local mode (no Docker)."""
from __future__ import annotations

from pathlib import Path

from app.config import Settings


def test_qdrant_url_defaults_to_none():
    settings = Settings(_env_file=None)
    assert settings.qdrant_url is None


def test_qdrant_url_can_still_be_set_explicitly():
    settings = Settings(_env_file=None, QDRANT_URL="http://localhost:6333")
    assert settings.qdrant_url == "http://localhost:6333"


def test_qdrant_local_path_is_under_data_dir():
    settings = Settings(_env_file=None, DATA_DIR="/tmp/some-data-dir")
    assert settings.qdrant_local_path == Path("/tmp/some-data-dir") / "qdrant_local"
