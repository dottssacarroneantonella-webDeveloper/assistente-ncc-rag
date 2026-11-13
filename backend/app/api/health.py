"""Stato del servizio (RF-15): database, coda e indice RAG."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.deps import AppState, get_state
from app.api.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health(state: AppState = Depends(get_state)) -> JSONResponse:
    try:
        with state.db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False
    queue_ok = await state.queue.ping()
    index_ready = state.engine.is_ready
    healthy = database_ok and queue_ok
    body = HealthOut(
        status="ok" if healthy and index_ready else "degraded",
        version=__version__,
        database=database_ok,
        queue=queue_ok,
        index_ready=index_ready,
    )
    return JSONResponse(status_code=200 if healthy else 503, content=body.model_dump())
