import pytest

from app.core.auth import create_session_token, hash_password, read_session_token, verify_password
from tests.conftest import ADMIN_EMAIL, login


def test_password_hashing() -> None:
    hashed = hash_password("una-password-lunga")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "una-password-lunga")
    assert not verify_password(hashed, "sbagliata")
    assert not verify_password(None, "qualsiasi")
    assert not verify_password("non-un-hash", "qualsiasi")


def test_short_password_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("corta")


def test_session_token_roundtrip_and_tampering() -> None:
    import uuid

    admin_id = uuid.uuid4()
    token = create_session_token(admin_id, "segreto", hours=1)
    assert read_session_token(token, "segreto") == admin_id
    assert read_session_token(token, "altro-segreto") is None
    assert read_session_token(token + "x", "segreto") is None
    assert read_session_token(create_session_token(admin_id, "segreto", hours=-1), "segreto") is None


def test_login_sets_secure_cookies(client) -> None:
    response = login(client)
    assert response.status_code == 204
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("session="))
    csrf_cookie = next(c for c in cookies if c.startswith("csrf_token="))
    assert "HttpOnly" in session_cookie and "SameSite=strict" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert client.get("/api/v1/auth/me").json() == {"email": ADMIN_EMAIL}


def test_email_is_case_insensitive(client) -> None:
    assert login(client, email=ADMIN_EMAIL.upper()).status_code == 204


def test_wrong_credentials(client) -> None:
    response = login(client, password="password-sbagliata")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    unknown = login(client, email="nessuno@example.com")
    assert unknown.json()["error"]["message"] == response.json()["error"]["message"]


def test_sixth_attempt_is_rate_limited(client) -> None:
    for _ in range(5):
        assert login(client, password="password-sbagliata").status_code == 401
    blocked = login(client)  # anche con la password giusta
    assert blocked.status_code == 429
    assert blocked.json()["error"]["details"]["retry_after_seconds"] > 0


def test_me_requires_login(client) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_forged_cookie_rejected(client) -> None:
    import uuid

    forged = create_session_token(uuid.uuid4(), "chiave-sbagliata", hours=1)
    client.cookies.set("session", forged, path="/api")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_requires_csrf_and_clears_session(admin) -> None:
    token = admin.headers.pop("X-CSRF-Token")
    assert admin.post("/api/v1/auth/logout").status_code == 403
    admin.headers["X-CSRF-Token"] = token
    assert admin.post("/api/v1/auth/logout").status_code == 204
    assert admin.get("/api/v1/auth/me").status_code == 401


def test_admin_not_created_without_credentials(settings) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    no_admin = settings.model_copy(update={"admin_email": None, "admin_password": None})
    with TestClient(create_app(no_admin)) as client:
        assert login(client).status_code == 401
