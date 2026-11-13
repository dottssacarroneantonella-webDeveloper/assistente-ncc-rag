"""Componenti condivisi da API (worker integrato) e worker separato."""

from __future__ import annotations

from app.channels.base import Channel
from app.channels.web import WebChannel
from app.core.config import Settings


def build_channels(settings: Settings) -> dict[str, Channel]:
    channels: dict[str, Channel] = {"web": WebChannel()}
    if settings.whatsapp_configured:
        from app.channels.whatsapp import WhatsAppChannel

        channels["whatsapp"] = WhatsAppChannel(settings)
    return channels
