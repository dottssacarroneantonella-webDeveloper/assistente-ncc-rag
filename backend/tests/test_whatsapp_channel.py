"""Invio tramite Graph API con trasporto HTTP simulato (httpx.MockTransport)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.channels.base import OutgoingReply
from app.channels.whatsapp import DeliveryError, WhatsAppChannel
from app.core.config import Settings


def make_settings() -> Settings:
    return Settings(
        whatsapp_enabled=True,
        meta_access_token="token-finto",
        meta_phone_number_id="123456",
        meta_app_secret="s",
        meta_verify_token="v",
        meta_graph_version="v21.0",
    )


REPLY = OutgoingReply(conversation_id="c", message_id="m", body="Costa 85 euro.", recipient="393331234567")


@pytest.mark.asyncio
async def test_sends_text_message() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    channel = WhatsAppChannel(make_settings(), transport=httpx.MockTransport(handler), backoff_seconds=0)
    await channel.deliver(REPLY)
    await channel.close()
    [request] = requests
    assert request.url == "https://graph.facebook.com/v21.0/123456/messages"
    assert request.headers["Authorization"] == "Bearer token-finto"
    assert json.loads(request.content) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "393331234567",
        "type": "text",
        "text": {"preview_url": False, "body": "Costa 85 euro."},
    }


@pytest.mark.asyncio
async def test_retries_on_server_errors_then_succeeds() -> None:
    codes = iter([503, 429, 200])
    channel = WhatsAppChannel(
        make_settings(),
        transport=httpx.MockTransport(lambda r: httpx.Response(next(codes), json={})),
        backoff_seconds=0,
    )
    await channel.deliver(REPLY)
    await channel.close()


@pytest.mark.asyncio
async def test_client_error_is_not_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(401, json={"error": {"message": "token scaduto"}})

    channel = WhatsAppChannel(make_settings(), transport=httpx.MockTransport(handler), backoff_seconds=0)
    with pytest.raises(DeliveryError, match="401"):
        await channel.deliver(REPLY)
    await channel.close()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_network_errors_exhaust_attempts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("rete giù")

    channel = WhatsAppChannel(
        make_settings(), transport=httpx.MockTransport(handler), attempts=2, backoff_seconds=0
    )
    with pytest.raises(DeliveryError, match="rete"):
        await channel.deliver(REPLY)
    await channel.close()


@pytest.mark.asyncio
async def test_missing_recipient() -> None:
    channel = WhatsAppChannel(make_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(DeliveryError):
        await channel.deliver(OutgoingReply("c", "m", "x"))
    await channel.close()


def test_long_body_is_truncated() -> None:
    channel = WhatsAppChannel(make_settings())
    payload = channel._payload(OutgoingReply("c", "m", "a" * 5000, recipient="39"))
    assert len(payload["text"]["body"]) == 4096  # type: ignore[index]
