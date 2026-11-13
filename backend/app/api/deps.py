"""Dipendenze condivise dagli endpoint (risorse create nel lifespan)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import Database
from app.queue.base import MessageQueue
from app.rag.engine import RagEngine


@dataclass
class AppState:
    settings: Settings
    db: Database
    queue: MessageQueue
    engine: RagEngine


def get_state(request: Request) -> AppState:
    return request.app.state.services  # type: ignore[no-any-return]


def get_session(request: Request) -> Iterator[Session]:
    with get_state(request).db.session() as session:
        yield session
