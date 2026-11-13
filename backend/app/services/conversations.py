"""Operazioni su conversazioni e messaggi."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.db.models import Conversation, Message, MessageSource, UnansweredQuestion
from app.rag.engine import SourceRef


class ConversationNotFoundError(LookupError):
    """La conversazione non esiste."""


def create_conversation(session: Session, channel: str = "web") -> Conversation:
    conversation = Conversation(channel=channel)
    session.add(conversation)
    session.flush()
    return conversation


def get_conversation(session: Session, conversation_id: uuid.UUID) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(str(conversation_id))
    return conversation


def add_incoming(
    session: Session,
    conversation: Conversation,
    body: str,
    kind: str = "text",
    external_id: str | None = None,
) -> Message:
    """Salva un messaggio in entrata con stato ``received``."""
    message = Message(
        conversation_id=conversation.id,
        direction="in",
        kind=kind,
        body=body[:4096],
        status="received",
        external_id=external_id,
    )
    conversation.last_message_at = utcnow()
    session.add(message)
    session.flush()
    return message


def add_reply(
    session: Session,
    incoming: Message,
    body: str,
    status: str,
    generator: str,
    sources: Sequence[SourceRef] = (),
    processing_ms: int | None = None,
) -> Message:
    """Salva la risposta collegata alla domanda, con le eventuali fonti."""
    reply = Message(
        conversation_id=incoming.conversation_id,
        direction="out",
        kind="text",
        body=body[:4096],
        status=status,
        generator=generator,
        in_reply_to=incoming.id,
        processing_ms=processing_ms,
    )
    reply.sources = [
        MessageSource(rank=i, source_file=s.file, page=s.page, score=s.score, excerpt=s.excerpt)
        for i, s in enumerate(sources, start=1)
    ]
    session.add(reply)
    conversation = session.get(Conversation, incoming.conversation_id)
    if conversation is not None:
        conversation.last_message_at = utcnow()
    session.flush()
    return reply


def record_unanswered(session: Session, incoming: Message, best_score: float | None) -> None:
    session.add(UnansweredQuestion(message_id=incoming.id, best_score=best_score))


def list_messages(
    session: Session, conversation_id: uuid.UUID, after: uuid.UUID | None = None
) -> list[Message]:
    """Messaggi della conversazione in ordine cronologico, opzionalmente dopo un messaggio dato."""
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .options(selectinload(Message.sources))
        .order_by(Message.created_at, Message.direction)
    )
    if after is not None:
        pivot = session.get(Message, after)
        if pivot is not None and pivot.conversation_id == conversation_id:
            query = query.where(Message.created_at > pivot.created_at)
    return list(session.scalars(query))


def delete_conversation_messages(
    session: Session, conversation_id: uuid.UUID, keep: uuid.UUID | None = None
) -> int:
    """Cancella i messaggi di una conversazione (RF-17), tranne eventualmente ``keep``
    (il comando "CANCELLA DATI" stesso, a cui segue la conferma). Fonti e domande aperte
    vengono eliminate a cascata."""
    query = delete(Message).where(Message.conversation_id == conversation_id)
    if keep is not None:
        query = query.where(Message.id != keep)
    result = session.execute(query)
    return result.rowcount or 0
