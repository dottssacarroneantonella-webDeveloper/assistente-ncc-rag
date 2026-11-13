"""Webhook della WhatsApp Cloud API (RF-02, RF-03, RF-05).

Il webhook deve rispondere a Meta in meno di un secondo (RNF-01): qui si verifica la
firma, si salva il messaggio e lo si mette in coda. La risposta la prepara il worker.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AppState, get_state
from app.api.errors import ApiError
from app.channels.whatsapp_payload import InboundWhatsApp, parse_webhook
from app.core.logging import log_event
from app.core.security import hash_contact, verify_meta_signature
from app.db.models import Conversation, Message
from app.queue.base import EVENT_MESSAGE_RECEIVED, Event
from app.services import conversations as conv

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)


def _require_enabled(state: AppState) -> None:
    if not state.settings.whatsapp_configured:
        raise ApiError(404, "whatsapp_disabled", "Il canale WhatsApp non è configurato")


@router.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    mode: str = Query(default="", alias="hub.mode"),
    token: str = Query(default="", alias="hub.verify_token"),
    challenge: str = Query(default="", alias="hub.challenge"),
    state: AppState = Depends(get_state),
) -> PlainTextResponse:
    """Handshake di Meta quando si registra l'URL del webhook."""
    _require_enabled(state)
    expected = state.settings.meta_verify_token or ""
    if mode != "subscribe" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise ApiError(403, "forbidden", "Token di verifica non valido")
    return PlainTextResponse(challenge)


def _conversation_for(session: Session, sender: str, key: str) -> Conversation:
    contact_hash, hint = hash_contact(sender, key)
    conversation = session.scalar(
        select(Conversation)
        .where(Conversation.channel == "whatsapp", Conversation.contact_hash == contact_hash)
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    if conversation is None:
        conversation = Conversation(channel="whatsapp", contact_hash=contact_hash, contact_hint=hint)
        session.add(conversation)
        session.flush()
    return conversation


def _store(state: AppState, inbound: InboundWhatsApp) -> str | None:
    """Salva il messaggio; restituisce il suo ID oppure None se è un duplicato (RF-05)."""
    try:
        with state.db.session() as session:
            if session.scalar(select(Message.id).where(Message.external_id == inbound.wamid)):
                return None
            conversation = _conversation_for(session, inbound.sender, state.settings.contact_hash_key)
            body = inbound.text if inbound.kind == "text" else f"[{inbound.kind}]"
            message = conv.add_incoming(
                session, conversation, body, kind=inbound.kind, external_id=inbound.wamid
            )
            return str(message.id)
    except IntegrityError:  # stesso wamid arrivato in parallelo
        return None


@router.post("/webhook")
async def receive_webhook(request: Request, state: AppState = Depends(get_state)) -> dict[str, str]:
    _require_enabled(state)
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_signature(body, signature, state.settings.meta_app_secret or ""):
        log_event(logger, "whatsapp.bad_signature")
        raise ApiError(401, "invalid_signature", "Firma del webhook non valida")
    try:
        payload = json.loads(body)
    except ValueError:
        raise ApiError(400, "bad_request", "Corpo JSON non valido") from None

    queued = duplicates = 0
    for inbound in parse_webhook(payload):
        message_id = await asyncio.to_thread(_store, state, inbound)
        if message_id is None:
            duplicates += 1
            continue
        # il numero viaggia solo nell'evento (serve per rispondere), mai nel database
        await state.queue.publish(
            Event(EVENT_MESSAGE_RECEIVED, {"message_id": message_id, "to": inbound.sender})
        )
        queued += 1
    log_event(logger, "whatsapp.webhook", queued=queued, duplicates=duplicates)
    return {"status": "ok"}
