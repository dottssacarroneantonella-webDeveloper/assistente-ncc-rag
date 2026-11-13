"""Lettura dei payload webhook della WhatsApp Cloud API.

Struttura (semplificata) inviata da Meta::

    {"object": "whatsapp_business_account",
     "entry": [{"changes": [{"field": "messages",
                             "value": {"messages": [{"from": "39333...", "id": "wamid...",
                                                     "type": "text", "text": {"body": "..."}}],
                                       "statuses": [...]}}]}]}

Le notifiche di stato (``statuses``: inviato, consegnato, letto) non sono messaggi del
cliente e vengono ignorate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# tipo WhatsApp → valore della colonna messages.kind
_KINDS = {
    "text": "text",
    "button": "text",
    "interactive": "text",
    "audio": "audio",
    "voice": "audio",
    "image": "image",
    "sticker": "image",
    "video": "other",
    "document": "other",
    "location": "location",
    "contacts": "other",
}


@dataclass(frozen=True)
class InboundWhatsApp:
    wamid: str
    sender: str
    kind: str
    text: str


def _text_of(message: dict[str, Any]) -> str:
    kind = message.get("type")
    if kind == "text":
        return str(message.get("text", {}).get("body", ""))
    if kind == "button":
        return str(message.get("button", {}).get("text", ""))
    if kind == "interactive":
        interactive = message.get("interactive", {})
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return str(reply.get("title", ""))
    return ""


def parse_webhook(payload: Any) -> list[InboundWhatsApp]:
    """Estrae i messaggi in arrivo. I payload malformati producono una lista vuota."""
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return []
    messages: list[InboundWhatsApp] = []
    for entry in payload.get("entry") or []:
        for change in (entry or {}).get("changes") or []:
            if (change or {}).get("field") != "messages":
                continue
            for message in (change.get("value") or {}).get("messages") or []:
                wamid, sender = message.get("id"), message.get("from")
                if not wamid or not sender:
                    continue
                kind = _KINDS.get(str(message.get("type")), "other")
                text = _text_of(message).strip()
                if kind == "text" and not text:
                    kind = "other"
                messages.append(InboundWhatsApp(wamid=str(wamid), sender=str(sender), kind=kind, text=text))
    return messages
