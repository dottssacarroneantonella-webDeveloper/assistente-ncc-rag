import asyncio

import pytest
from app.queue.base import Event, TransientError
from app.queue.memory import InMemoryQueue


@pytest.mark.asyncio
async def test_event_is_handled() -> None:
    queue, seen = InMemoryQueue(retry_base_seconds=0), []

    async def handler(event: Event) -> None:
        seen.append(event.payload["n"])

    async def on_failure(event: Event, error: Exception) -> None:  # pragma: no cover
        raise AssertionError("non doveva fallire")

    await queue.start_consuming(handler, on_failure)
    await queue.publish(Event("t", {"n": 1}))
    await queue.publish(Event("t", {"n": 2}))
    await queue.join()
    await queue.close()
    assert seen == [1, 2]


@pytest.mark.asyncio
async def test_transient_errors_are_retried_then_succeed() -> None:
    queue, attempts = InMemoryQueue(max_attempts=3, retry_base_seconds=0), []

    async def handler(event: Event) -> None:
        attempts.append(event.attempt)
        if event.attempt < 3:
            raise TransientError("LLM non raggiungibile")

    async def on_failure(event: Event, error: Exception) -> None:  # pragma: no cover
        raise AssertionError("non doveva fallire")

    await queue.start_consuming(handler, on_failure)
    await queue.publish(Event("t", {}))
    await queue.join()
    await queue.close()
    assert attempts == [1, 2, 3]


@pytest.mark.asyncio
async def test_on_failure_after_last_attempt() -> None:
    queue, failures = InMemoryQueue(max_attempts=2, retry_base_seconds=0), []

    async def handler(event: Event) -> None:
        raise TransientError("sempre giù")

    async def on_failure(event: Event, error: Exception) -> None:
        failures.append(event.attempt)

    await queue.start_consuming(handler, on_failure)
    await queue.publish(Event("t", {}))
    await queue.join()
    await queue.close()
    assert failures == [2]


@pytest.mark.asyncio
async def test_permanent_error_is_not_retried() -> None:
    queue, calls, failures = InMemoryQueue(retry_base_seconds=0), [], []

    async def handler(event: Event) -> None:
        calls.append(1)
        raise ValueError("dato non valido")

    async def on_failure(event: Event, error: Exception) -> None:
        failures.append(type(error).__name__)

    await queue.start_consuming(handler, on_failure)
    await queue.publish(Event("t", {}))
    await asyncio.wait_for(queue.join(), timeout=5)
    await queue.close()
    assert calls == [1] and failures == ["ValueError"]
