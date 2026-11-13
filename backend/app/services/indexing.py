"""Job di indicizzazione dei documenti (RF-11, RF-14)."""

from __future__ import annotations

import logging
import threading
import uuid

from sqlalchemy import select, update

from app.core.config import Settings
from app.core.logging import log_event
from app.db.base import utcnow
from app.db.models import Document, IndexJob
from app.db.session import Database
from app.rag.engine import RagEngine

logger = logging.getLogger(__name__)


class JobAlreadyRunningError(RuntimeError):
    """C'è già un job in coda o in esecuzione (RF-11)."""


_job_lock = threading.Lock()


def create_job(db: Database, triggered_by: uuid.UUID | None = None) -> uuid.UUID:
    """Crea un job ``queued``; se ce n'è già uno attivo solleva ``JobAlreadyRunningError``."""
    with _job_lock, db.session() as session:
        active = session.scalar(
            select(IndexJob.id).where(IndexJob.status.in_(("queued", "running"))).limit(1)
        )
        if active is not None:
            raise JobAlreadyRunningError(str(active))
        job = IndexJob(status="queued", triggered_by=triggered_by)
        session.add(job)
        session.flush()
        return job.id


def run_job(db: Database, engine: RagEngine, settings: Settings, job_id: uuid.UUID) -> None:
    """Esegue la reindicizzazione e aggiorna stato del job e dei documenti."""
    with db.session() as session:
        job = session.get(IndexJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status, job.started_at = "running", utcnow()
    try:
        report = engine.rebuild(settings.docs_dir)
    except Exception as exc:
        logger.exception("Indicizzazione fallita")
        with db.session() as session:
            session.execute(
                update(IndexJob)
                .where(IndexJob.id == job_id)
                .values(status="failed", error=str(exc)[:2000], finished_at=utcnow())
            )
        return
    with db.session() as session:
        session.execute(
            update(IndexJob)
            .where(IndexJob.id == job_id)
            .values(status="done", chunks=report.chunks, finished_at=utcnow())
        )
        session.execute(update(Document).values(status="indexed"))
    log_event(logger, "index.done", documents=report.documents, chunks=report.chunks)


def recover_interrupted_jobs(db: Database) -> int:
    """All'avvio: un job rimasto ``queued``/``running`` è stato interrotto da un riavvio."""
    with db.session() as session:
        result = session.execute(
            update(IndexJob)
            .where(IndexJob.status.in_(("queued", "running")))
            .values(status="failed", error="Interrotto dal riavvio del servizio", finished_at=utcnow())
        )
        return result.rowcount or 0
