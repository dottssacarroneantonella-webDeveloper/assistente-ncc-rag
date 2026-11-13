import uuid

from app.db.models import Document, Message, UnansweredQuestion
from sqlalchemy import func, select


def test_seed_documents_loaded(client) -> None:
    db = client.app.state.services.db
    with db.session() as session:
        names = set(session.scalars(select(Document.stored_name)))
        statuses = set(session.scalars(select(Document.status)))
    assert names == {"listino_2026.pdf", "condizioni_servizio.pdf", "faq.pdf"}
    assert statuses == {"indexed"}


def test_create_conversation_returns_welcome(client) -> None:
    response = client.post("/api/v1/chat/conversations")
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert "NCC Levante Transfer" in body["welcome"]


def test_answer_with_price_and_source(ask) -> None:
    result = ask("Quanto costa il transfer dall'aeroporto di Bari a Monopoli?")
    reply = result["reply"]
    assert reply["status"] == "answered"
    assert "85 euro" in reply["body"]
    assert reply["sources"][0]["file"] == "listino_2026.pdf"
    assert reply["sources"][0]["page"] == 1


def test_question_is_marked_answered(ask) -> None:
    result = ask("Accettate animali a bordo?")
    question = next(m for m in result["items"] if m["direction"] == "in")
    assert question["status"] == "answered"
    assert "animali" in result["reply"]["body"].lower()


def test_unknown_question_is_recorded(client, ask) -> None:
    result = ask("Qual è la capitale della Francia?")
    reply = result["reply"]
    assert reply["status"] == "not_found"
    assert "titolare" in reply["body"]
    with client.app.state.services.db.session() as session:
        assert session.scalar(select(func.count()).select_from(UnansweredQuestion)) == 1


def test_greeting_does_not_use_rag(ask) -> None:
    reply = ask("Ciao")["reply"]
    assert reply["status"] == "sent"
    assert "Puoi chiedermi" in reply["body"]
    assert reply["sources"] == []


def test_delete_data_erases_conversation(client, ask) -> None:
    first = ask("Si può pagare con carta?")
    conversation_id = first["conversation_id"]
    result = ask("CANCELLA DATI", conversation_id=conversation_id)
    bodies = [m["body"] for m in result["items"]]
    assert not any("carta" in b.lower() for b in bodies)
    assert "cancellato" in result["reply"]["body"]


def test_after_parameter_returns_only_new_messages(client, ask) -> None:
    first = ask("Quali lingue parlano gli autisti?")
    conversation_id = first["conversation_id"]
    last_id = first["items"][-1]["id"]
    second = ask("Dove mi aspetta l'autista in aeroporto?", conversation_id=conversation_id)
    newer = client.get(
        f"/api/v1/chat/conversations/{conversation_id}/messages", params={"after": last_id}
    ).json()["items"]
    assert len(second["items"]) == 4
    assert [m["direction"] for m in newer] == ["in", "out"]


def test_empty_message_rejected(client) -> None:
    conversation_id = client.post("/api/v1/chat/conversations").json()["id"]
    response = client.post(f"/api/v1/chat/conversations/{conversation_id}/messages", json={"text": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_too_long_message_rejected(client, settings) -> None:
    conversation_id = client.post("/api/v1/chat/conversations").json()["id"]
    text = "a" * (settings.max_question_chars + 1)
    response = client.post(f"/api/v1/chat/conversations/{conversation_id}/messages", json={"text": text})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "question_too_long"


def test_unknown_conversation_returns_404(client) -> None:
    response = client.get(f"/api/v1/chat/conversations/{uuid.uuid4()}/messages")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_invalid_conversation_id_returns_422(client) -> None:
    response = client.get("/api/v1/chat/conversations/non-un-uuid/messages")
    assert response.status_code == 422


def test_message_body_stored(client, ask) -> None:
    ask("Quanto costa il van?")
    with client.app.state.services.db.session() as session:
        bodies = set(session.scalars(select(Message.body).where(Message.direction == "in")))
    assert "Quanto costa il van?" in bodies
