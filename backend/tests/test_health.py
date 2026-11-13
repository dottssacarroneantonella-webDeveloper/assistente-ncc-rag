def test_health_ok_after_seed(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True and body["queue"] is True and body["index_ready"] is True


def test_security_headers(client) -> None:
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_unknown_route_uses_error_format(client) -> None:
    response = client.get("/api/v1/non-esiste")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
