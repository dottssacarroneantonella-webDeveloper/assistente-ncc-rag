from app.channels.whatsapp_payload import parse_webhook


def wrap(*messages: dict, statuses: list | None = None) -> dict:
    value: dict = {"messaging_product": "whatsapp", "messages": list(messages)}
    if statuses is not None:
        value["statuses"] = statuses
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": value}]}],
    }


def test_text_message() -> None:
    payload = wrap({"from": "393331234567", "id": "wamid.1", "type": "text", "text": {"body": " Ciao "}})
    [message] = parse_webhook(payload)
    assert (message.wamid, message.sender, message.kind, message.text) == (
        "wamid.1",
        "393331234567",
        "text",
        "Ciao",
    )


def test_non_text_types() -> None:
    payload = wrap(
        {"from": "39", "id": "a", "type": "audio", "audio": {"id": "m"}},
        {"from": "39", "id": "b", "type": "image", "image": {"id": "m"}},
        {"from": "39", "id": "c", "type": "location", "location": {"latitude": 41.1}},
        {"from": "39", "id": "d", "type": "reaction", "reaction": {"emoji": "👍"}},
    )
    assert [m.kind for m in parse_webhook(payload)] == ["audio", "image", "location", "other"]


def test_interactive_reply_is_text() -> None:
    payload = wrap(
        {
            "from": "39",
            "id": "x",
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "1", "title": "Listino"}},
        }
    )
    [message] = parse_webhook(payload)
    assert message.kind == "text" and message.text == "Listino"


def test_status_notifications_are_ignored() -> None:
    assert parse_webhook(wrap(statuses=[{"id": "wamid.1", "status": "delivered"}])) == []


def test_malformed_payloads() -> None:
    assert parse_webhook(None) == []
    assert parse_webhook({"object": "page"}) == []
    assert parse_webhook({"object": "whatsapp_business_account", "entry": [{"changes": [None]}]}) == []
    assert parse_webhook(wrap({"type": "text", "text": {"body": "senza id"}})) == []


def test_empty_text_becomes_other() -> None:
    [message] = parse_webhook(wrap({"from": "39", "id": "e", "type": "text", "text": {"body": "  "}}))
    assert message.kind == "other"
