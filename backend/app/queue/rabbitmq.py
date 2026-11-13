"""Coda RabbitMQ (aio-pika): durevole, ack manuale, ritentativi con ritardo e coda di errore.

Topologia (prefisso configurabile, default ``ncc``)::

    ncc.events                coda principale, durevole
    ncc.events.retry.<ms>     una coda per ogni ritardo (2000, 4000, ...): ha un TTL e,
                              alla scadenza, rimanda il messaggio a ncc.events
                              (dead-letter verso l'exchange predefinito)
    ncc.events.dlq            coda di errore: eventi falliti dopo l'ultimo tentativo

Il messaggio viene confermato (ack) solo dopo che il worker ha salvato la risposta:
se il worker si ferma a metà, RabbitMQ lo riconsegna (RNF-03). Il worker è idempotente,
quindi una riconsegna non produce risposte doppie.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustChannel, AbstractRobustConnection

from app.core.logging import log_event
from app.queue.base import Event, FailureHandler, Handler, MessageQueue, TransientError

logger = logging.getLogger(__name__)
ATTEMPT_HEADER = "x-attempt"


def encode(event: Event) -> aio_pika.Message:
    body = json.dumps({"type": event.type, "payload": event.payload}).encode()
    return aio_pika.Message(
        body=body,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        headers={**event.headers, ATTEMPT_HEADER: event.attempt},
    )


def decode(message: AbstractIncomingMessage) -> Event:
    data: dict[str, Any] = json.loads(message.body)
    headers = dict(message.headers or {})
    attempt = int(headers.pop(ATTEMPT_HEADER, 1) or 1)
    return Event(
        type=str(data["type"]),
        payload=dict(data.get("payload") or {}),
        attempt=attempt,
        headers={str(k): str(v) for k, v in headers.items() if not str(k).startswith("x-")},
    )


class RabbitMQQueue(MessageQueue):
    def __init__(
        self,
        url: str,
        prefix: str = "ncc",
        max_attempts: int = 3,
        retry_base_seconds: float = 2.0,
        prefetch: int = 4,
    ) -> None:
        self.url = url
        self.max_attempts = max_attempts
        self.retry_base_seconds = retry_base_seconds
        self.prefetch = prefetch
        self.main_queue = f"{prefix}.events"
        self.dead_letter_queue = f"{prefix}.events.dlq"
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._consumer_tag: str | None = None

    # --- topologia ---------------------------------------------------------------------

    def retry_delays_ms(self) -> list[int]:
        """Ritardi prima dei tentativi 2..max: 2000, 4000, 8000 ms con i valori predefiniti."""
        return [
            max(1, int(self.retry_base_seconds * 1000 * 2 ** (n - 1))) for n in range(1, self.max_attempts)
        ]

    def retry_queue(self, delay_ms: int) -> str:
        return f"{self.main_queue}.retry.{delay_ms}"

    async def connect(self) -> None:
        if self._channel is not None:
            return
        self._connection = await aio_pika.connect_robust(self.url)
        self._channel = await self._connection.channel()  # type: ignore[assignment]
        await self._channel.set_qos(prefetch_count=self.prefetch)
        await self._channel.declare_queue(self.main_queue, durable=True)
        await self._channel.declare_queue(self.dead_letter_queue, durable=True)
        for delay in set(self.retry_delays_ms()):
            await self._channel.declare_queue(
                self.retry_queue(delay),
                durable=True,
                arguments={
                    "x-message-ttl": delay,
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": self.main_queue,
                },
            )

    async def _send(self, event: Event, routing_key: str) -> None:
        await self.connect()
        assert self._channel is not None
        await self._channel.default_exchange.publish(encode(event), routing_key=routing_key)

    # --- interfaccia MessageQueue ----------------------------------------------------------

    async def publish(self, event: Event) -> None:
        await self._send(event, self.main_queue)

    async def start_consuming(self, handler: Handler, on_failure: FailureHandler) -> None:
        await self.connect()
        assert self._channel is not None
        queue = await self._channel.get_queue(self.main_queue)

        async def on_message(message: AbstractIncomingMessage) -> None:
            try:
                event = decode(message)
            except (ValueError, KeyError) as exc:
                logger.error("Messaggio illeggibile spostato nella coda di errore: %s", exc)
                await self._channel.default_exchange.publish(  # type: ignore[union-attr]
                    aio_pika.Message(body=message.body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                    routing_key=self.dead_letter_queue,
                )
                await message.ack()
                return
            try:
                await handler(event)
            except TransientError as exc:
                await self._retry_or_fail(event, exc, on_failure)
            except Exception as exc:
                logger.exception("Errore non recuperabile durante l'elaborazione dell'evento")
                await self._fail(event, exc, on_failure)
            await message.ack()

        self._consumer_tag = await queue.consume(on_message, no_ack=False)

    async def _retry_or_fail(self, event: Event, exc: Exception, on_failure: FailureHandler) -> None:
        if event.attempt >= self.max_attempts:
            await self._fail(event, exc, on_failure)
            return
        delay = self.retry_delays_ms()[event.attempt - 1]
        log_event(logger, "event.retry", type=event.type, attempt=event.attempt, delay_ms=delay)
        await self._send(event.retry(), self.retry_queue(delay))

    async def _fail(self, event: Event, exc: Exception, on_failure: FailureHandler) -> None:
        log_event(logger, "event.failed", type=event.type, attempts=event.attempt, error=str(exc))
        try:
            await on_failure(event, exc)
        finally:
            failed = Event(
                event.type, event.payload, event.attempt, {**event.headers, "error": str(exc)[:500]}
            )
            await self._send(failed, self.dead_letter_queue)

    async def ping(self) -> bool:
        return self._connection is not None and not self._connection.is_closed

    async def message_count(self, queue_name: str) -> int:
        """Numero di messaggi in attesa in una coda (usato nei test e nel monitoraggio)."""
        await self.connect()
        assert self._channel is not None
        declared = await self._channel.declare_queue(queue_name, durable=True, passive=True)
        return declared.declaration_result.message_count or 0

    async def purge(self) -> None:
        """Svuota tutte le code (solo per i test)."""
        await self.connect()
        assert self._channel is not None
        names = [self.main_queue, self.dead_letter_queue, *map(self.retry_queue, self.retry_delays_ms())]
        for name in names:
            queue = await self._channel.get_queue(name)
            await queue.purge()

    async def delete_topology(self) -> None:
        """Elimina le code (solo per i test)."""
        await self.connect()
        assert self._channel is not None
        names = [self.main_queue, self.dead_letter_queue, *map(self.retry_queue, self.retry_delays_ms())]
        for name in set(names):
            await self._channel.queue_delete(name)

    async def close(self) -> None:
        if self._channel is not None and self._consumer_tag is not None:
            try:
                queue = await self._channel.get_queue(self.main_queue)
                await queue.cancel(self._consumer_tag)
            except Exception:  # noqa: S110 - in chiusura gli errori non sono rilevanti
                pass
        if self._connection is not None:
            await self._connection.close()
        self._connection = self._channel = None
        self._consumer_tag = None
