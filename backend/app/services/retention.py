"""Conservazione dei dati (RF-16, RNF-07): le conversazioni inattive da più di
``RETENTION_DAYS`` giorni vengono eliminate con messaggi, fonti e domande collegate."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete

from app.core.logging import log_event
from app.db.base import utcnow
from app.db.models import Conversation
from app.db.session import Database

logger = logging.getLogger(__name__)


def purge_expired(db: Database, retention_days: int) -> int:
    """Elimina le conversazioni con ultimo messaggio più vecchio del limite. Restituisce il numero."""
    cutoff = utcnow() - timedelta(days=retention_days)
    with db.session() as session:
        result = session.execute(delete(Conversation).where(Conversation.last_message_at < cutoff))
        deleted = result.rowcount or 0
    log_event(logger, "retention.purged", conversations=deleted, days=retention_days)
    return deleted


async def run_periodically(db: Database, retention_days: int, interval_hours: float) -> None:
    """Esegue la pulizia all'avvio e poi a intervalli regolari (default ogni 24 ore)."""
    while True:
        try:
            await asyncio.to_thread(purge_expired, db, retention_days)
        except Exception:
            logger.exception("Pulizia dei dati non riuscita")
        await asyncio.sleep(interval_hours * 3600)
