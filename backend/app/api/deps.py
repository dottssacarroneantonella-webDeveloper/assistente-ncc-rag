"""Dipendenze condivise dagli endpoint (risorse create nel lifespan)."""

from __future__ import annotations

import hmac
from collections.abc import Iterator
from dataclasses import dataclass, field

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.core.auth import read_session_token
from app.core.config import Settings
from app.core.ratelimit import SlidingWindowLimiter
from app.db.models import AdminUser
from app.db.session import Database
from app.queue.base import MessageQueue
from app.rag.engine import RagEngine

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


@dataclass
class AppState:
    settings: Settings
    db: Database
    queue: MessageQueue
    engine: RagEngine
    login_limiter: SlidingWindowLimiter = field(init=False)

    def __post_init__(self) -> None:
        self.login_limiter = SlidingWindowLimiter(
            self.settings.login_max_attempts, self.settings.login_window_minutes * 60
        )


def get_state(request: Request) -> AppState:
    return request.app.state.services  # type: ignore[no-any-return]


def get_session(request: Request) -> Iterator[Session]:
    with get_state(request).db.session() as session:
        yield session


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "sconosciuto"


def require_admin(
    request: Request,
    state: AppState = Depends(get_state),
    session: Session = Depends(get_session),
) -> AdminUser:
    """Admin autenticato dal cookie di sessione; altrimenti 401."""
    token = request.cookies.get(SESSION_COOKIE)
    admin_id = read_session_token(token, state.settings.secret_key) if token else None
    admin = session.get(AdminUser, admin_id) if admin_id else None
    if admin is None:
        raise ApiError(401, "unauthorized", "Accesso richiesto")
    return admin


def require_csrf(request: Request) -> None:
    """Double-submit: l'header X-CSRF-Token deve coincidere con il cookie csrf_token."""
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get(CSRF_HEADER, "")
    if not cookie or not hmac.compare_digest(cookie.encode(), header.encode()):
        raise ApiError(403, "csrf_failed", "Token CSRF mancante o non valido")
