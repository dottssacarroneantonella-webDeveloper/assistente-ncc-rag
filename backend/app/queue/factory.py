"""Creazione della coda indicata in configurazione."""

from __future__ import annotations

from app.core.config import Settings
from app.queue.base import MessageQueue
from app.queue.memory import InMemoryQueue


def create_queue(settings: Settings) -> MessageQueue:
    if settings.queue_backend == "memory":
        return InMemoryQueue(settings.max_attempts, settings.retry_base_seconds)
    raise NotImplementedError("La coda RabbitMQ arriva nella fase F2: per ora usa QUEUE_BACKEND=memory.")
