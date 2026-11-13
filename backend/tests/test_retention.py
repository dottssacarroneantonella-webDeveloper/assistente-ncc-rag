from datetime import timedelta

from sqlalchemy import func, select

from app.db.base import utcnow
from app.db.models import Conversation, Message, MessageSource, UnansweredQuestion
from app.services.retention import purge_expired


def _age_conversation(db, conversation_id: str, days: int) -> None:
    import uuid

    with db.session() as session:
        conversation = session.get(Conversation, uuid.UUID(conversation_id))
        conversation.last_message_at = utcnow() - timedelta(days=days)


def counts(db) -> tuple[int, int, int, int]:
    with db.session() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (Conversation, Message, MessageSource, UnansweredQuestion)
        )


def test_old_conversations_are_deleted_with_everything_linked(client, ask) -> None:
    db = client.app.state.services.db
    old = ask("Quanto costa il transfer dall'aeroporto di Bari a Monopoli?")
    old_unknown = ask("Qual è la capitale della Francia?", conversation_id=old["conversation_id"])
    recent = ask("Accettate animali a bordo?")
    assert old_unknown["reply"]["status"] == "not_found"
    _age_conversation(db, old["conversation_id"], days=31)

    assert purge_expired(db, retention_days=30) == 1
    conversations, messages, sources, unanswered = counts(db)
    assert conversations == 1 and messages == 2 and unanswered == 0
    with db.session() as session:
        remaining = session.scalar(select(Conversation.id))
    assert str(remaining) == recent["conversation_id"]
    assert sources > 0  # fonti della conversazione recente


def test_recent_conversations_are_kept(client, ask) -> None:
    db = client.app.state.services.db
    result = ask("Si può pagare con carta?")
    _age_conversation(db, result["conversation_id"], days=29)
    assert purge_expired(db, retention_days=30) == 0
    assert counts(db)[0] == 1
