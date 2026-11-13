"""Fixture comuni: ogni test usa un database SQLite e un indice in una cartella temporanea."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from app.core.config import PROJECT_DIR, Settings
from app.main import create_app
from fastapi.testclient import TestClient


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
