"""Invio delle risposte con la WhatsApp Cloud API (Graph API di Meta).

Solo messaggi di testo, nella finestra di 24 ore aperta dal cliente: nessun template a
pagamento. Gli errori temporanei (rete, 429, 5xx) vengono ritentati qui, con attesa
crescente; gli errori definitivi (4xx, es. token scaduto) vengono registrati nel log.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.channels.base import Channel, OutgoingReply
from app.core.config import Settings
from app.core.logging import log_event

logger = logging.getLogger(__name__)
MAX_WHATSAPP_CHARS = 4096


class DeliveryError(Exception):
    """La risposta non è stata consegnata a WhatsApp."""


class WhatsAppChannel(Channel):
    name = "whatsapp"

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        attempts: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.settings = settings
        self.attempts = attempts
        self.backoff_seconds = backoff_seconds
        self._client = httpx.AsyncClient(
            base_url=settings.meta_graph_base_url,
            timeout=settings.meta_timeout_seconds,
            transport=transport,
        )

    @property
    def url(self) -> str:
        s = self.settings
        return f"/{s.meta_graph_version}/{s.meta_phone_number_id}/messages"

    def _payload(self, reply: OutgoingReply) -> dict[str, object]:
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": reply.recipient,
            "type": "text",
            "text": {"preview_url": False, "body": reply.body[:MAX_WHATSAPP_CHARS]},
        }

    async def deliver(self, reply: OutgoingReply) -> None:
        if not reply.recipient:
            raise DeliveryError("Destinatario mancante")
        headers = {"Authorization": f"Bearer {self.settings.meta_access_token}"}
        last_error: str = ""
        for attempt in range(1, self.attempts + 1):
            try:
                response = await self._client.post(self.url, json=self._payload(reply), headers=headers)
            except httpx.TransportError as exc:
                last_error = f"rete: {type(exc).__name__}"
            else:
                if response.status_code < 300:
                    log_event(logger, "whatsapp.sent", message=reply.message_id, attempt=attempt)
                    return
                last_error = f"HTTP {response.status_code}"
                if response.status_code != 429 and response.status_code < 500:
                    break  # errore definitivo: inutile ritentare
            if attempt < self.attempts:
                await asyncio.sleep(self.backoff_seconds * 2 ** (attempt - 1))
        log_event(logger, "whatsapp.delivery_failed", message=reply.message_id, error=last_error)
        raise DeliveryError(last_error)

    async def close(self) -> None:
        await self._client.aclose()
