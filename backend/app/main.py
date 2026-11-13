"""Punto di ingresso dell'API FastAPI.

All'avvio (lifespan):
1. crea lo schema se ``AUTO_CREATE_SCHEMA`` è attivo (demo e test; in produzione Alembic);
2. se non ci sono documenti carica i PDF di esempio e costruisce l'indice (RF-14);
3. con la coda in memoria avvia il worker nello stesso processo; con RabbitMQ il worker
   è un processo separato (``python -m app.worker``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app import __version__
from app.api import admin, auth, chat, health, whatsapp
from app.api.deps import AppState
from app.api.errors import register_error_handlers
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import Database
from app.queue.factory import create_queue
from app.rag.engine import RagEngine
from app.services import indexing
from app.services.admins import ensure_admin
from app.services.documents import seed_example_documents
from app.worker.processor import MessageProcessor
from app.worker.runtime import build_channels

logger = logging.getLogger(__name__)
API_PREFIX = "/api/v1"


def _bootstrap(state: AppState) -> None:
    """Crea l'admin, carica i documenti di esempio e indicizza se l'indice non esiste."""
    s = state.settings
    indexing.recover_interrupted_jobs(state.db)
    with state.db.session() as session:
        ensure_admin(session, s.admin_email, s.admin_password)
        seed_example_documents(session, s.seed_docs_dir, s.docs_dir)
    if not state.engine.is_ready and any(s.docs_dir.glob("*.pdf")):
        job_id = indexing.create_job(state.db)
        indexing.run_job(state.db, state.engine, s, job_id)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings)
        if settings.auto_create_schema:
            Base.metadata.create_all(db.engine)
        engine = RagEngine(settings)
        queue = create_queue(settings)
        state = AppState(settings=settings, db=db, queue=queue, engine=engine)
        app.state.services = state

        await asyncio.to_thread(_bootstrap, state)
        await queue.connect()

        channels = build_channels(settings)
        processor = MessageProcessor(db, engine, settings, channels)
        app.state.processor = processor
        # con la coda in memoria il worker gira nello stesso processo dell'API;
        # con RabbitMQ gira separato (python -m app.worker)
        if settings.queue_backend == "memory":
            await queue.start_consuming(processor.handle, processor.on_failure)
        logger.info("Avvio completato (versione %s, coda %s)", __version__, settings.queue_backend)
        try:
            yield
        finally:
            await queue.close()
            for channel in channels.values():
                await channel.close()
            db.engine.dispose()

    app = FastAPI(
        title="Assistente NCC con RAG",
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(chat.router, prefix=API_PREFIX)
    app.include_router(whatsapp.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)
    return app


app = create_app()
