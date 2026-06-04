"""Fixtures de teste — força modo MOCK (sem chave/rede) antes de importar o app."""

from __future__ import annotations

import os

os.environ.setdefault("ARGUS_LLM_MOCK", "1")
os.environ.setdefault("ARGUS_CORS_ORIGINS", "http://localhost:5173")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    return TestClient(app)
