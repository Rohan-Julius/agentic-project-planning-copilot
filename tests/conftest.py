"""Shared fixtures: isolated in-memory DB + tmp document storage per test."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database.session import get_session
from app.main import app
from app.models.base import Base
from app.services.vector_service import VectorService, get_vector_service


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _get_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    test_settings = Settings(data_dir=tmp_path / "data")
    test_vector_service = VectorService(client=QdrantClient(location=":memory:"))

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_vector_service] = lambda: test_vector_service
    with TestClient(app) as test_client:
        # Exposed so integration tests can verify retrieval (via the tools layer, which
        # isn't itself behind FastAPI DI) against the exact same in-memory Qdrant the API
        # endpoints just wrote to/deleted from.
        test_client.vector_service = test_vector_service
        yield test_client
    app.dependency_overrides.clear()
