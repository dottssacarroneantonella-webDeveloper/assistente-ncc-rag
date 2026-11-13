"""Fixture comuni: ogni test usa un database SQLite e un indice in una cartella temporanea."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import PROJECT_DIR, Settings
from app.main import create_app

ADMIN_EMAIL = "admin@ncc-levante.example"
ADMIN_PASSWORD = "password-di-test-lunga"  # noqa: S105 - solo per i test


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        rag_index_dir=tmp_path / "index",
        docs_dir=tmp_path / "docs",
        seed_docs_dir=PROJECT_DIR / "examples" / "ncc-docs",
        queue_backend="memory",
        answer_generator="extractive",
        rag_embedder="tfidf",
        retry_base_seconds=0,
        max_attempts=3,
        admin_email=ADMIN_EMAIL,
        admin_password=ADMIN_PASSWORD,
        secret_key="chiave-di-test-per-i-jwt-abbastanza-lunga",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def ask(client: TestClient) -> Callable[[str], dict]:
    """Invia una domanda in una nuova conversazione e attende la risposta del worker."""

    def _ask(text: str, conversation_id: str | None = None, timeout: float = 15.0) -> dict:
        if conversation_id is None:
            conversation_id = client.post("/api/v1/chat/conversations").json()["id"]
        sent = client.post(f"/api/v1/chat/conversations/{conversation_id}/messages", json={"text": text})
        assert sent.status_code == 202, sent.text
        message_id = sent.json()["message_id"]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            items = client.get(f"/api/v1/chat/conversations/{conversation_id}/messages").json()["items"]
            replies = [m for m in items if m["in_reply_to"] == message_id]
            if replies:
                return {"conversation_id": conversation_id, "reply": replies[0], "items": items}
            time.sleep(0.05)
        raise AssertionError("Nessuna risposta dal worker entro il tempo limite")

    return _ask


def login(client: TestClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.fixture
def admin(client: TestClient) -> TestClient:
    """Client autenticato come admin, con l'header CSRF già impostato."""
    response = login(client)
    assert response.status_code == 204, response.text
    client.headers["X-CSRF-Token"] = client.cookies["csrf_token"]
    return client
