"""Canale chat web: la risposta è già nel database, il browser la legge con il polling."""

from __future__ import annotations

from app.channels.base import Channel, OutgoingReply


class WebChannel(Channel):
    name = "web"

    async def deliver(self, reply: OutgoingReply) -> None:  # noqa: D102 - niente da consegnare
        return None
