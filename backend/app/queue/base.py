"""Interfaccia della coda di messaggi.

Il webhook e la chat pubblicano eventi; il worker li consuma. L'implementazione si
sceglie da configurazione (``QUEUE_BACKEND``): RabbitMQ in locale e in produzione,
coda in memoria per la demo gratuita e per i test.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

EVENT_MESSAGE_RECEIVED = "message.received"
EVENT_INDEX_REQUESTED = "index.requested"


@dataclass(frozen=True)
class Event:
    """Evento in coda. ``attempt`` parte da 1 e cresce a ogni ritentativo."""

    type: str
    payload: dict[str, Any]
    attempt: int = 1
    headers: dict[str, str] = field(default_factory=dict)

    def retry(self) -> Event:
        return Event(type=self.type, payload=self.payload, attempt=self.attempt + 1, headers=self.headers)


class TransientError(Exception):
    """Errore temporaneo (es. LLM non raggiungibile): l'evento va ritentato."""


Handler = Callable[[Event], Awaitable[None]]
FailureHandler = Callable[[Event, Exception], Awaitable[None]]


class MessageQueue(ABC):
    """Coda con ritentativi e gestione dei fallimenti definitivi."""

    async def connect(self) -> None:  # noqa: B027 - le code in memoria non hanno nulla da aprire
        """Apre la connessione (se serve). Chiamato all'avvio di API e worker."""

    @abstractmethod
    async def publish(self, event: Event) -> None:
        """Mette in coda un evento."""

    @abstractmethod
    async def start_consuming(self, handler: Handler, on_failure: FailureHandler) -> None:
        """Avvia il consumo: ``handler`` per ogni evento, ``on_failure`` dopo l'ultimo tentativo."""

    @abstractmethod
    async def close(self) -> None:
        """Ferma il consumo e libera le risorse."""

    async def ping(self) -> bool:
        """True se la coda è raggiungibile (usato da /health)."""
        return True
