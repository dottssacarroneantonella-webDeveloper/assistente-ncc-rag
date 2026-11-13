"""Creazione della coda indicata in configurazione."""

from __future__ import annotations

from app.core.config import Settings
from app.queue.base import MessageQueue
from app.queue.memory import InMemoryQueue


def create_queue(settings: Settings) -> MessageQueue:
    if settings.queue_backend == "rabbitmq":
        from app.queue.rabbitmq import RabbitMQQueue  # import pigro: aio-pika serve solo qui

        return RabbitMQQueue(
            settings.rabbitmq_url,
            prefix=settings.queue_prefix,
            max_attempts=settings.max_attempts,
            retry_base_seconds=settings.retry_base_seconds,
            prefetch=settings.worker_prefetch,
        )
    return InMemoryQueue(settings.max_attempts, settings.retry_base_seconds)
