"""Chat web simulata (RF-06): stessa pipeline di WhatsApp, consegna tramite polling."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AppState, get_session, get_state
from app.api.errors import ApiError
from app.api.schemas import (
    ConversationOut,
    MessageAccepted,
    MessageIn,
    MessageOut,
    MessagesOut,
    SourceOut,
)
from app.db.models import Message
from app.queue.base import EVENT_MESSAGE_RECEIVED, Event
from app.services import conversations as conv
from app.worker.intents import welcome_message

router = APIRouter(prefix="/chat", tags=["chat"])


def _load_conversation(session: Session, conversation_id: uuid.UUID):  # type: ignore[no-untyped-def]
    try:
        conversation = conv.get_conversation(session, conversation_id)
    except conv.ConversationNotFoundError:
        raise ApiError(404, "conversation_not_found", "Conversazione inesistente") from None
    if conversation.channel != "web":
        raise ApiError(404, "conversation_not_found", "Conversazione inesistente")
    return conversation


def _to_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        direction=message.direction,  # type: ignore[arg-type]
        body=message.body,
        status=message.status,
        in_reply_to=message.in_reply_to,
        sources=[
            SourceOut(rank=s.rank, file=s.source_file, page=s.page, score=s.score, excerpt=s.excerpt)
            for s in message.sources
        ],
        created_at=message.created_at,
    )


@router.post("/conversations", status_code=201, response_model=ConversationOut)
def create_conversation(
    state: AppState = Depends(get_state), session: Session = Depends(get_session)
) -> ConversationOut:
    conversation = conv.create_conversation(session, channel="web")
    return ConversationOut(id=conversation.id, welcome=welcome_message(state.settings.business_name))


@router.post("/conversations/{conversation_id}/messages", status_code=202, response_model=MessageAccepted)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageIn,
    state: AppState = Depends(get_state),
) -> MessageAccepted:
    text = payload.text.strip()
    if not text:
        raise ApiError(422, "validation_error", "Il messaggio è vuoto")
    if len(text) > state.settings.max_question_chars:
        raise ApiError(
            422,
            "question_too_long",
            f"La domanda supera i {state.settings.max_question_chars} caratteri",
        )
    with state.db.session() as session:
        conversation = _load_conversation(session, conversation_id)
        message = conv.add_incoming(session, conversation, text)
        message_id = message.id
    # pubblicazione dopo il commit: il worker trova sempre il messaggio nel database
    await state.queue.publish(Event(EVENT_MESSAGE_RECEIVED, {"message_id": str(message_id)}))
    return MessageAccepted(message_id=message_id)


@router.get("/conversations/{conversation_id}/messages", response_model=MessagesOut)
def list_messages(
    conversation_id: uuid.UUID,
    after: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
) -> MessagesOut:
    _load_conversation(session, conversation_id)
    messages = conv.list_messages(session, conversation_id, after=after)
    return MessagesOut(items=[_to_out(m) for m in messages])
