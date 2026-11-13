"""Interfaccia dei canali di uscita.

Il worker produce la risposta e la salva nel database; il canale decide come
consegnarla. Per la chat web non serve fare nulla (il browser legge la risposta
con il polling), per WhatsApp (Fase 2) il canale chiamerà la Graph API di Meta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class OutgoingReply:
    conversation_id: str
    message_id: str
    body: str


class Channel(ABC):
    name: str

    @abstractmethod
    async def deliver(self, reply: OutgoingReply) -> None:
        """Consegna la risposta all'utente. Può sollevare ``TransientError``."""
