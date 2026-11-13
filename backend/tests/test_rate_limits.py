def test_chat_message_rate_limit(client, settings) -> None:
    conversation_id = client.post("/api/v1/chat/conversations").json()["id"]
    url = f"/api/v1/chat/conversations/{conversation_id}/messages"
    for i in range(settings.chat_messages_per_minute):
        assert client.post(url, json={"text": f"Domanda {i}"}).status_code == 202
    blocked = client.post(url, json={"text": "Una di troppo"})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) > 0


def test_daily_limit(settings) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    limited = settings.model_copy(update={"chat_messages_per_day": 2, "chat_messages_per_minute": 50})
    with TestClient(create_app(limited)) as client:
        conversation_id = client.post("/api/v1/chat/conversations").json()["id"]
        url = f"/api/v1/chat/conversations/{conversation_id}/messages"
        assert client.post(url, json={"text": "uno"}).status_code == 202
        assert client.post(url, json={"text": "due"}).status_code == 202
        response = client.post(url, json={"text": "tre"})
        assert response.status_code == 429
        assert "giornaliero" in response.json()["error"]["message"]


def test_conversation_creation_limit(settings) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    limited = settings.model_copy(update={"chat_conversations_per_hour": 2})
    with TestClient(create_app(limited)) as client:
        assert client.post("/api/v1/chat/conversations").status_code == 201
        assert client.post("/api/v1/chat/conversations").status_code == 201
        assert client.post("/api/v1/chat/conversations").status_code == 429


def test_limiter_drops_empty_keys() -> None:
    from app.core.ratelimit import SlidingWindowLimiter

    class Clock:
        now = 0.0

        def __call__(self) -> float:
            return self.now

    clock = Clock()
    limiter = SlidingWindowLimiter(1, 10, clock=clock)
    assert limiter.check_and_hit("a") and not limiter.check_and_hit("a")
    clock.now = 11
    assert not limiter.is_blocked("a")
    assert len(limiter) == 0
