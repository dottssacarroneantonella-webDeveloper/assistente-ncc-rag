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
    assert response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert response.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in response.headers  # solo fuori dallo sviluppo


def test_docs_page_is_not_blocked_by_csp(client) -> None:
    response = client.get("/api/v1/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers


def test_unknown_route_uses_error_format(client) -> None:
    response = client.get("/api/v1/non-esiste")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
