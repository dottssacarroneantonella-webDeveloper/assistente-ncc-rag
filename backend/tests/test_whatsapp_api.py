"""Webhook WhatsApp end-to-end con canale di uscita finto (nessuna chiamata a Meta)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.channels.base import Channel, OutgoingReply
from app.core.config import Settings
from app.core.security import sign_meta_body
from app.db.models import Conversation, Message
from app.main import create_app
from app.worker.intents import NON_TEXT_REPLY

SECRET = "segreto-app-di-test"  # noqa: S105 - valori fittizi
VERIFY = "token-verifica-di-test"  # noqa: S105
NUMBER = "393331234567"
URL = "/api/v1/whatsapp/webhook"


class FakeWhatsApp(Channel):
    name = "whatsapp"

    def __init__(self) -> None:
        self.sent: list[OutgoingReply] = []

    async def deliver(self, reply: OutgoingReply) -> None:
        self.sent.append(reply)


@pytest.fixture
def wa_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "whatsapp_enabled": True,
            "meta_access_token": "token-finto",
            "meta_phone_number_id": "123456",
            "meta_app_secret": SECRET,
            "meta_verify_token": VERIFY,
            "contact_hash_key": "chiave-test",
        }
    )


@pytest.fixture
def wa(wa_settings: Settings):
    with TestClient(create_app(wa_settings)) as client:
        fake = FakeWhatsApp()
        client.app.state.processor.channels["whatsapp"] = fake
        yield client, fake


def message(
    wamid: str,
    text: str | None = "Quanto costa il transfer dall'aeroporto di Bari a Monopoli?",
    kind: str = "text",
) -> dict:
    item: dict = {"from": NUMBER, "id": wamid, "timestamp": "1731500000", "type": kind}
    if kind == "text":
        item["text"] = {"body": text}
    else:
        item[kind] = {"id": "media-1"}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": {"messages": [item]}}]}],
    }


def post(client: TestClient, payload: dict, signature: str | None = "auto"):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if signature == "auto":
        headers["X-Hub-Signature-256"] = sign_meta_body(body, SECRET)
    elif signature is not None:
        headers["X-Hub-Signature-256"] = signature
    return client.post(URL, content=body, headers=headers)


def wait_for(fake: FakeWhatsApp, count: int = 1, timeout: float = 15.0) -> list[OutgoingReply]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(fake.sent) >= count:
            return fake.sent
        time.sleep(0.05)
    raise AssertionError(f"Attese {count} risposte, ricevute {len(fake.sent)}")


def test_verify_handshake(wa) -> None:
    client, _ = wa
    ok = client.get(URL, params={"hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = client.get(URL, params={"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"})
    assert bad.status_code == 403


def test_text_message_is_answered_on_whatsapp(wa) -> None:
    client, fake = wa
    response = post(client, message("wamid.A"))
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    [reply] = wait_for(fake)
    assert reply.recipient == NUMBER
    assert "85 euro" in reply.body
    with client.app.state.services.db.session() as session:
        conversation = session.scalar(select(Conversation))
        assert conversation.channel == "whatsapp"
        assert conversation.contact_hint == "4567"
        assert NUMBER not in (conversation.contact_hash or "")
        statuses = set(session.scalars(select(Message.status)))
    assert statuses == {"answered"}


def test_number_is_never_stored(wa) -> None:
    client, fake = wa
    post(client, message("wamid.B"))
    wait_for(fake)
    db_path = Path(client.app.state.services.settings.database_url.removeprefix("sqlite:///"))
    assert NUMBER.encode() not in db_path.read_bytes()


def test_missing_or_invalid_signature_is_rejected(wa) -> None:
    client, fake = wa
    assert post(client, message("wamid.C"), signature=None).status_code == 401
    assert post(client, message("wamid.C"), signature="sha256=" + "0" * 64).status_code == 401
    assert post(client, message("wamid.C"), signature="sha256=" + "0" * 64).json()["error"]["code"] == (
        "invalid_signature"
    )
    with client.app.state.services.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Message)) == 0
    assert fake.sent == []


def test_duplicate_wamid_is_queued_once(wa) -> None:
    client, fake = wa
    assert post(client, message("wamid.D")).status_code == 200
    assert post(client, message("wamid.D")).status_code == 200
    wait_for(fake)
    time.sleep(0.3)
    assert len(fake.sent) == 1
    with client.app.state.services.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Message).where(Message.direction == "in")) == 1


def test_audio_gets_write_please_reply(wa) -> None:
    client, fake = wa
    post(client, message("wamid.E", kind="audio"))
    [reply] = wait_for(fake)
    assert reply.body == NON_TEXT_REPLY


def test_same_number_reuses_conversation(wa) -> None:
    client, fake = wa
    post(client, message("wamid.F", "Ciao"))
    post(client, message("wamid.G", "Accettate animali a bordo?"))
    wait_for(fake, 2)
    with client.app.state.services.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 1


def test_delete_data_on_whatsapp(wa) -> None:
    client, fake = wa
    post(client, message("wamid.H", "Si può pagare con carta?"))
    wait_for(fake, 1)
    post(client, message("wamid.I", "CANCELLA DATI"))
    replies = wait_for(fake, 2)
    assert "cancellato" in replies[1].body
    with client.app.state.services.db.session() as session:
        bodies = list(session.scalars(select(Message.body)))
    assert not any("carta" in b for b in bodies)


def test_status_only_payload_is_accepted(wa) -> None:
    client, fake = wa
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {"statuses": [{"status": "read"}]}}]}],
    }
    assert post(client, payload).status_code == 200
    assert fake.sent == []


def test_invalid_json_is_rejected(wa) -> None:
    client, _ = wa
    body = b"non json"
    response = client.post(URL, content=body, headers={"X-Hub-Signature-256": sign_meta_body(body, SECRET)})
    assert response.status_code == 400


def test_webhook_disabled_by_default(client) -> None:
    assert client.post(URL, content=b"{}").status_code == 404
    assert client.get(URL).json()["error"]["code"] == "whatsapp_disabled"


def test_webhook_is_fast(wa) -> None:
    """RNF-01: il webhook risponde subito anche se il worker sta ancora lavorando."""
    client, fake = wa
    durations = []
    for i in range(20):
        start = time.perf_counter()
        assert post(client, message(f"wamid.perf{i}", "Quali lingue parlano gli autisti?")).status_code == 200
        durations.append(time.perf_counter() - start)
    durations.sort()
    assert durations[int(len(durations) * 0.95) - 1] < 1.0
    wait_for(fake, 20, timeout=60)
