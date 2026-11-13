"""Coda in memoria basata su asyncio, con ritentativi a intervallo crescente.

Va bene per la demo (un solo processo) e per i test. Gli eventi in coda si perdono se
il processo si ferma: per l'affidabilità completa si usa RabbitMQ (RNF-03).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.core.logging import log_event
from app.queue.base import Event, FailureHandler, Handler, MessageQueue, TransientError

logger = logging.getLogger(__name__)


class InMemoryQueue(MessageQueue):
    def __init__(self, max_attempts: int = 3, retry_base_seconds: float = 2.0) -> None:
        self.max_attempts = max_attempts
        self.retry_base_seconds = retry_base_seconds
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._consumer: asyncio.Task[None] | None = None
        self._pending: set[asyncio.Task[None]] = set()

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)

    async def start_consuming(self, handler: Handler, on_failure: FailureHandler) -> None:
        self._consumer = asyncio.create_task(self._run(handler, on_failure), name="in-memory-consumer")

    async def _run(self, handler: Handler, on_failure: FailureHandler) -> None:
        while True:
            event = await self._queue.get()
            try:
                await handler(event)
            except TransientError as exc:
                await self._retry_or_fail(event, exc, on_failure)
            except Exception as exc:  # errore non recuperabile: niente ritentativi
                logger.exception("Errore non recuperabile durante l'elaborazione dell'evento")
                await on_failure(event, exc)
            finally:
                self._queue.task_done()

    async def _retry_or_fail(self, event: Event, exc: Exception, on_failure: FailureHandler) -> None:
        if event.attempt >= self.max_attempts:
            log_event(logger, "event.failed", type=event.type, attempts=event.attempt)
            await on_failure(event, exc)
            return
        delay = self.retry_base_seconds * (2 ** (event.attempt - 1))  # 2, 4, 8 secondi
        log_event(logger, "event.retry", type=event.type, attempt=event.attempt, delay_s=delay)
        task = asyncio.create_task(self._delayed_publish(event.retry(), delay))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _delayed_publish(self, event: Event, delay: float) -> None:
        await asyncio.sleep(delay)
        await self.publish(event)

    async def join(self) -> None:
        """Attende che la coda sia vuota e che non ci siano ritentativi in sospeso (per i test)."""
        while True:
            await self._queue.join()
            if not self._pending:
                return
            await asyncio.gather(*list(self._pending), return_exceptions=True)

    async def close(self) -> None:
        for task in [self._consumer, *self._pending]:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._consumer = None
        self._pending.clear()
