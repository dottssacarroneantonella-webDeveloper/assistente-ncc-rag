"""Integrazione con un RabbitMQ reale (in CI tramite container di servizio).

Si eseguono solo se è impostata RABBITMQ_TEST_URL, ad esempio:
    RABBITMQ_TEST_URL=amqp://guest:guest@localhost:5672/ pytest tests/test_rabbitmq.py
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from app.queue.base import Event, TransientError

URL = os.environ.get("RABBITMQ_TEST_URL")
pytestmark = pytest.mark.skipif(not URL, reason="RABBITMQ_TEST_URL non impostata")


async def make_queue(max_attempts: int = 3):
    from app.queue.rabbitmq import RabbitMQQueue

    queue = RabbitMQQueue(
        URL or "", prefix=f"test-{uuid.uuid4().hex[:8]}", max_attempts=max_attempts, retry_base_seconds=0.1
    )
    await queue.connect()
    return queue


async def until(condition, timeout: float = 10.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not condition():
        if loop.time() > deadline:
            raise AssertionError("condizione non raggiunta in tempo")
        await asyncio.sleep(0.05)


async def cleanup(queue) -> None:
    await queue.delete_topology()
    await queue.close()


def test_retry_delays() -> None:
    from app.queue.rabbitmq import RabbitMQQueue

    queue = RabbitMQQueue("amqp://x", max_attempts=4, retry_base_seconds=2)
    assert queue.retry_delays_ms() == [2000, 4000, 8000]


@pytest.mark.asyncio
async def test_publish_and_consume() -> None:
    queue = await make_queue()
    seen: list[dict] = []

    async def handler(event: Event) -> None:
        seen.append(event.payload)

    async def on_failure(event: Event, error: Exception) -> None:  # pragma: no cover
        raise AssertionError(error)

    await queue.start_consuming(handler, on_failure)
    await queue.publish(Event("message.received", {"message_id": "1"}))
    await until(lambda: seen == [{"message_id": "1"}])
    assert await queue.ping()
    await cleanup(queue)


@pytest.mark.asyncio
async def test_transient_error_retried_with_delay_queue() -> None:
    queue = await make_queue()
    attempts: list[int] = []

    async def handler(event: Event) -> None:
        attempts.append(event.attempt)
        if event.attempt < 3:
            raise TransientError("LLM giù")

    async def on_failure(event: Event, error: Exception) -> None:  # pragma: no cover
        raise AssertionError(error)

    await queue.start_consuming(handler, on_failure)
    await queue.publish(Event("message.received", {"message_id": "2"}))
    await until(lambda: attempts == [1, 2, 3])
    await cleanup(queue)


@pytest.mark.asyncio
async def test_final_failure_goes_to_dead_letter_queue() -> None:
    queue = await make_queue(max_attempts=2)
    failures: list[int] = []

    async def handler(event: Event) -> None:
        raise TransientError("sempre giù")

    async def on_failure(event: Event, error: Exception) -> None:
        failures.append(event.attempt)

    await queue.start_consuming(handler, on_failure)
    await queue.publish(Event("message.received", {"message_id": "3"}))
    await until(lambda: failures == [2])
    await asyncio.sleep(0.2)
    assert await queue.message_count(queue.dead_letter_queue) == 1
    assert await queue.message_count(queue.main_queue) == 0
    await cleanup(queue)


@pytest.mark.asyncio
async def test_unacked_message_is_redelivered_after_crash() -> None:
    """RNF-03: se il worker si ferma prima dell'ack, il messaggio non va perso."""
    first = await make_queue()
    started = asyncio.Event()

    async def stuck(event: Event) -> None:
        started.set()
        await asyncio.sleep(3600)  # simula un worker che si blocca

    async def on_failure(event: Event, error: Exception) -> None:  # pragma: no cover
        pass

    await first.start_consuming(stuck, on_failure)
    await first.publish(Event("message.received", {"message_id": "4"}))
    await asyncio.wait_for(started.wait(), 10)
    await first._connection.close()  # "crash": connessione chiusa senza ack

    from app.queue.rabbitmq import RabbitMQQueue

    second = RabbitMQQueue(URL or "", prefix=first.main_queue.removesuffix(".events"), retry_base_seconds=0.1)
    seen: list[str] = []

    async def handler(event: Event) -> None:
        seen.append(event.payload["message_id"])

    await second.start_consuming(handler, on_failure)
    await until(lambda: seen == ["4"])
    await cleanup(second)
