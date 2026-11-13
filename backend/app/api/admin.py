"""Area admin: documenti, reindicizzazione, conversazioni, domande senza risposta
(RF-10, RF-11, RF-12, RF-13). Tutti gli endpoint richiedono la sessione admin; quelli che
modificano dati richiedono anche il token CSRF."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.chat import message_out
from app.api.deps import AppState, get_session, get_state, require_admin, require_csrf
from app.api.errors import ApiError
from app.api.schemas import (
    AdminMessageOut,
    ConversationDetail,
    ConversationSummary,
    DocumentOut,
    DocumentsOut,
    IndexJobOut,
    IndexJobsOut,
    Page,
    UnansweredOut,
    UnansweredPatch,
)
from app.core.logging import log_event
from app.db.base import utcnow
from app.db.models import AdminUser, Conversation, Document, IndexJob, Message, UnansweredQuestion
from app.services import indexing
from app.services.documents import register_file

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)
PDF_MAGIC = b"%PDF-"


# --- documenti ------------------------------------------------------------------------------


@router.get("/documents", response_model=DocumentsOut)
def list_documents(session: Session = Depends(get_session)) -> DocumentsOut:
    documents = session.scalars(select(Document).order_by(Document.uploaded_at.desc()))
    return DocumentsOut(items=[DocumentOut.model_validate(d) for d in documents])


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks, total = [], 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise ApiError(413, "payload_too_large", f"Il file supera {limit // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/documents", status_code=201, response_model=DocumentOut, dependencies=[Depends(require_csrf)])
async def upload_document(
    file: UploadFile = File(...),
    state: AppState = Depends(get_state),
    admin: AdminUser = Depends(require_admin),
) -> DocumentOut:
    if file.content_type != "application/pdf":
        raise ApiError(415, "unsupported_media_type", "Sono accettati solo file PDF")
    data = await _read_limited(file, state.settings.max_upload_mb * 1024 * 1024)
    if not data.startswith(PDF_MAGIC):
        raise ApiError(415, "unsupported_media_type", "Il file non è un PDF valido")
    name = Path(file.filename or "documento.pdf").name
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / (name if name.lower().endswith(".pdf") else f"{name}.pdf")
        source.write_bytes(data)
        with state.db.session() as session:
            document = register_file(session, source, state.settings.docs_dir)
            if document is None:
                raise ApiError(409, "duplicate_document", "Documento già presente")
            document.uploaded_by = admin.id
            out = DocumentOut.model_validate(document)
    log_event(logger, "admin.document_uploaded", admin=str(admin.id), document=str(out.id), size=len(data))
    return out


@router.delete("/documents/{document_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_document(
    document_id: uuid.UUID,
    state: AppState = Depends(get_state),
    admin: AdminUser = Depends(require_admin),
) -> None:
    with state.db.session() as session:
        document = session.get(Document, document_id)
        if document is None:
            raise ApiError(404, "document_not_found", "Documento inesistente")
        (state.settings.docs_dir / document.stored_name).unlink(missing_ok=True)
        session.delete(document)
    log_event(logger, "admin.document_deleted", admin=str(admin.id), document=str(document_id))


# --- reindicizzazione -----------------------------------------------------------------------


@router.post("/index-jobs", status_code=202, response_model=IndexJobOut, dependencies=[Depends(require_csrf)])
def start_index_job(
    background: BackgroundTasks,
    state: AppState = Depends(get_state),
    admin: AdminUser = Depends(require_admin),
) -> IndexJobOut:
    try:
        job_id = indexing.create_job(state.db, triggered_by=admin.id)
    except indexing.JobAlreadyRunningError:
        raise ApiError(409, "job_already_running", "Una reindicizzazione è già in corso") from None
    # eseguito dopo la risposta, in un thread: l'API resta reattiva durante l'indicizzazione
    background.add_task(indexing.run_job, state.db, state.engine, state.settings, job_id)
    log_event(logger, "admin.index_started", admin=str(admin.id), job=str(job_id))
    with state.db.session() as session:
        return IndexJobOut.model_validate(session.get(IndexJob, job_id))


@router.get("/index-jobs", response_model=IndexJobsOut)
def list_index_jobs(
    limit: int = Query(default=5, ge=1, le=50), session: Session = Depends(get_session)
) -> IndexJobsOut:
    jobs = session.scalars(select(IndexJob).order_by(IndexJob.created_at.desc()).limit(limit))
    return IndexJobsOut(items=[IndexJobOut.model_validate(j) for j in jobs])


@router.get("/index-jobs/{job_id}", response_model=IndexJobOut)
def get_index_job(job_id: uuid.UUID, session: Session = Depends(get_session)) -> IndexJobOut:
    job = session.get(IndexJob, job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "Job inesistente")
    return IndexJobOut.model_validate(job)


# --- conversazioni --------------------------------------------------------------------------


def _summary(conversation: Conversation, messages: int) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        channel=conversation.channel,
        contact=f"***{conversation.contact_hint}" if conversation.contact_hint else None,
        messages=messages,
        started_at=conversation.started_at,
        last_message_at=conversation.last_message_at,
    )


@router.get("/conversations", response_model=Page[ConversationSummary])
def list_conversations(
    channel: Literal["web", "whatsapp"] | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> Page[ConversationSummary]:
    counts = (
        select(Message.conversation_id, func.count().label("n")).group_by(Message.conversation_id).subquery()
    )
    query = select(Conversation, func.coalesce(counts.c.n, 0)).outerjoin(
        counts, counts.c.conversation_id == Conversation.id
    )
    total_query = select(func.count()).select_from(Conversation)
    if channel:
        query = query.where(Conversation.channel == channel)
        total_query = total_query.where(Conversation.channel == channel)
    rows = session.execute(
        query.order_by(Conversation.last_message_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return Page[ConversationSummary](
        items=[_summary(c, n) for c, n in rows],
        total=session.scalar(total_query) or 0,
        page=page,
        size=size,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(
    conversation_id: uuid.UUID, session: Session = Depends(get_session)
) -> ConversationDetail:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise ApiError(404, "conversation_not_found", "Conversazione inesistente")
    messages = list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.sources))
            .order_by(Message.created_at, Message.direction)
        )
    )
    return ConversationDetail(
        conversation=_summary(conversation, len(messages)),
        messages=[
            AdminMessageOut(
                **message_out(m).model_dump(),
                kind=m.kind,
                generator=m.generator,
                processing_ms=m.processing_ms,
            )
            for m in messages
        ],
    )


# --- domande senza risposta -----------------------------------------------------------------


def _unanswered_out(item: UnansweredQuestion) -> UnansweredOut:
    return UnansweredOut(
        id=item.id,
        question=item.message.body,
        conversation_id=item.message.conversation_id,
        asked_at=item.message.created_at,
        best_score=item.best_score,
        status=item.status,  # type: ignore[arg-type]
        note=item.note,
        handled_at=item.handled_at,
    )


@router.get("/unanswered", response_model=Page[UnansweredOut])
def list_unanswered(
    status: Literal["open", "handled"] = "open",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> Page[UnansweredOut]:
    base = select(UnansweredQuestion).where(UnansweredQuestion.status == status)
    items = session.scalars(
        base.join(UnansweredQuestion.message)
        .options(selectinload(UnansweredQuestion.message))
        .order_by(Message.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    return Page[UnansweredOut](items=[_unanswered_out(i) for i in items], total=total, page=page, size=size)


@router.patch("/unanswered/{item_id}", response_model=UnansweredOut, dependencies=[Depends(require_csrf)])
def update_unanswered(
    item_id: uuid.UUID,
    payload: UnansweredPatch,
    state: AppState = Depends(get_state),
    admin: AdminUser = Depends(require_admin),
) -> UnansweredOut:
    with state.db.session() as session:
        item = session.get(UnansweredQuestion, item_id)
        if item is None:
            raise ApiError(404, "unanswered_not_found", "Domanda inesistente")
        item.status = payload.status
        item.note = payload.note.strip() if payload.note else None
        if payload.status == "handled":
            item.handled_by, item.handled_at = admin.id, utcnow()
        else:
            item.handled_by = item.handled_at = None
        session.flush()
        out = _unanswered_out(item)
    log_event(
        logger, "admin.unanswered_updated", admin=str(admin.id), item=str(item_id), status=payload.status
    )
    return out
