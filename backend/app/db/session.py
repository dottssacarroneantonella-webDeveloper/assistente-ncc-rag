"""Motore e sessioni del database."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    """Crea il motore; su SQLite abilita le chiavi esterne (ON DELETE CASCADE)."""
    connect_args: dict[str, object] = {}
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False
        path = settings.database_url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
    if settings.is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


class Database:
    """Contenitore di motore e fabbrica di sessioni, creato una volta all'avvio."""

    def __init__(self, settings: Settings) -> None:
        self.engine = build_engine(settings)
        self._factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Sessione con commit automatico se tutto va bene, rollback in caso di errore."""
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
