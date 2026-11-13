"""Elaborazione dei messaggi in arrivo (consumer della coda).

Flusso per ogni evento ``message.received``:
1. carica il messaggio e lo segna ``processing``;
2. riconosce l'intento (saluto, contenuto non testuale, cancellazione dati, domanda);
3. per le domande interroga il motore RAG; se non trova nulla registra la domanda
   tra quelle senza risposta (RF-12);
4. salva la risposta con le fonti e la consegna tramite il canale.

Gli errori temporanei (``TransientError``) vengono ritentati dalla coda; dopo
l'ultimo tentativo ``on_failure`` salva un messaggio di scuse (RF-08).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass

from app.channels.base import Channel, OutgoingReply
from app.core.config import Settings
from app.core.logging import log_event
from app.db.models import Message
from app.db.session import Database
from app.queue.base import EVENT_MESSAGE_RECEIVED, Event
from app.rag.engine import RagEngine
from app.services import conversations as conv
from app.worker.intents import (
    DELETE_REPLY,
    FAILURE_REPLY,
    NON_TEXT_REPLY,
    NOT_FOUND_SUFFIX,
    Intent,
    detect_intent,
    welcome_message,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Outcome:
    conversation_id: uuid.UUID
    reply_id: uuid.UUID
    body: str
    channel: str


class MessageProcessor:
    def __init__(
        self,
        db: Database,
        engine: RagEngine,
        settings: Settings,
        channels: dict[str, Channel],
    ) -> None:
        self.db = db
        self.engine = engine
        self.settings = settings
        self.channels = channels

    # --- punti di ingresso usati dalla coda -------------------------------------------------

    async def handle(self, event: Event) -> None:
        if event.type != EVENT_MESSAGE_RECEIVED:
            logger.warning("Evento ignorato: %s", event.type)
            return
        outcome = await asyncio.to_thread(self._process, event)
        if outcome is not None:
            await self._deliver(outcome)

    async def on_failure(self, event: Event, error: Exception) -> None:
        log_event(logger, "message.failed", attempt=event.attempt, error=str(error))
        outcome = await asyncio.to_thread(self._mark_failed, event)
        if outcome is not None:
            await self._deliver(outcome)

    # --- logica sincrona (eseguita in un thread) ---------------------------------------------

    def _load(self, session, event: Event) -> Message | None:  # type: ignore[no-untyped-def]
        try:
            message_id = uuid.UUID(str(event.payload["message_id"]))
        except (KeyError, ValueError):
            logger.error("Evento senza message_id valido: %s", event.payload)
            return None
        return session.get(Message, message_id)

    def _process(self, event: Event) -> _Outcome | None:
        started = time.perf_counter()
        with self.db.session() as session:
            incoming = self._load(session, event)
            if incoming is None or incoming.status not in ("received", "processing"):
                return None  # già elaborato (consegna duplicata) o inesistente
            incoming.status = "processing"
            incoming.attempts = (incoming.attempts or 0) + 1
            channel = incoming.conversation.channel
            body, kind = incoming.body, incoming.kind
            conversation_id = incoming.conversation_id

        intent = detect_intent(body, kind)
        best_score: float | None = None

        if intent is Intent.DELETE_DATA:
            with self.db.session() as session:
                incoming = self._load(session, event)
                if incoming is None:
                    return None
                conv.delete_conversation_messages(session, conversation_id, keep=incoming.id)
                incoming.status = "answered"
                reply = conv.add_reply(session, incoming, DELETE_REPLY, "sent", "intent")
                log_event(logger, "conversation.erased", conversation=str(conversation_id))
                return _Outcome(conversation_id, reply.id, reply.body, channel)

        if intent is Intent.GREETING:
            text, status, generator, sources, answered = (
                welcome_message(self.settings.business_name),
                "sent",
                "intent",
                [],
                True,
            )
        elif intent is Intent.NON_TEXT:
            text, status, generator, sources, answered = NON_TEXT_REPLY, "sent", "intent", [], True
        else:
            result = self.engine.answer(body)  # può sollevare TransientError → retry
            answered = result.answered
            text = result.text if answered else f"{result.text}{NOT_FOUND_SUFFIX}".strip()
            status = "answered" if answered else "not_found"
            generator, sources = result.generator, result.sources
            best_score = result.best_score

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        with self.db.session() as session:
            incoming = self._load(session, event)
            if incoming is None:
                return None
            incoming.status = status if status != "sent" else "answered"
            reply = conv.add_reply(
                session, incoming, text, status, generator, sources, processing_ms=elapsed_ms
            )
            if intent is Intent.QUESTION and not answered:
                conv.record_unanswered(session, incoming, best_score)
            log_event(
                logger,
                "message.answered",
                intent=intent.value,
                status=status,
                sources=len(sources),
                ms=elapsed_ms,
            )
            return _Outcome(incoming.conversation_id, reply.id, reply.body, channel)

    def _mark_failed(self, event: Event) -> _Outcome | None:
        with self.db.session() as session:
            incoming = self._load(session, event)
            if incoming is None or incoming.status not in ("received", "processing"):
                return None
            incoming.status = "failed"
            reply = conv.add_reply(session, incoming, FAILURE_REPLY, "failed", "intent")
            return _Outcome(incoming.conversation_id, reply.id, reply.body, incoming.conversation.channel)

    async def _deliver(self, outcome: _Outcome) -> None:
        channel = self.channels.get(outcome.channel)
        if channel is None:
            logger.error("Canale sconosciuto: %s", outcome.channel)
            return
        await channel.deliver(
            OutgoingReply(str(outcome.conversation_id), str(outcome.reply_id), outcome.body)
        )
