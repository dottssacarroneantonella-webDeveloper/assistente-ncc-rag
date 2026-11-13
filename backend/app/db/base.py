"""Base dichiarativa di SQLAlchemy e tipi comuni."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Ora corrente in UTC, con fuso orario."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Classe base di tutti i modelli."""
