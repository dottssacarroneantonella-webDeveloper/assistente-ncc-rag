from sqlalchemy import select

from app.db.models import Message
from app.queue.base import TransientError
from app.worker.intents import FAILURE_REPLY


def test_llm_down_produces_apology_after_retries(client, ask, monkeypatch) -> None:
    engine = client.app.state.services.engine
    calls = []

    def broken_answer(question: str):
        calls.append(question)
        raise TransientError("Ollama non raggiungibile")

    monkeypatch.setattr(engine, "answer", broken_answer)
    result = ask("Quanto costa il transfer per Lecce?")
    reply = result["reply"]
    assert reply["status"] == "failed"
    assert reply["body"] == FAILURE_REPLY
    assert len(calls) == 3  # MAX_ATTEMPTS
    with client.app.state.services.db.session() as session:
        question = session.scalar(select(Message).where(Message.direction == "in"))
        assert question.status == "failed"
        assert question.attempts == 3


def test_duplicate_event_is_ignored(client, ask) -> None:
    """Una consegna duplicata dello stesso evento non produce una seconda risposta."""
    import asyncio

    from app.queue.base import EVENT_MESSAGE_RECEIVED, Event

    result = ask("Quanto costa il servizio a ore?")
    message_id = result["reply"]["in_reply_to"]
    processor = client.app.state.processor
    asyncio.run(processor.handle(Event(EVENT_MESSAGE_RECEIVED, {"message_id": message_id})))
    items = client.get(f"/api/v1/chat/conversations/{result['conversation_id']}/messages").json()["items"]
    assert sum(1 for m in items if m["in_reply_to"] == message_id) == 1


def test_processing_time_recorded(client, ask) -> None:
    result = ask("Il seggiolino per bambini è gratuito?")
    with client.app.state.services.db.session() as session:
        reply = session.get(Message, __import__("uuid").UUID(result["reply"]["id"]))
        assert reply.processing_ms is not None and reply.processing_ms >= 0
        assert reply.generator == "extractive"
