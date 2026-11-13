"""Login e logout dell'admin (RF-09).

Il JWT di sessione sta in un cookie HttpOnly (JavaScript non può leggerlo, quindi un
eventuale XSS non può rubarlo), Secure e SameSite=Strict. Il cookie csrf_token invece è
leggibile dal frontend, che lo rimanda nell'header X-CSRF-Token (double-submit).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AppState,
    client_ip,
    get_session,
    get_state,
    require_admin,
    require_csrf,
)
from app.api.errors import ApiError
from app.api.schemas import AdminOut, LoginIn
from app.core.auth import create_session_token, new_csrf_token
from app.core.logging import log_event
from app.db.models import AdminUser
from app.services.admins import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _set_cookies(response: Response, state: AppState, token: str, csrf: str) -> None:
    max_age = state.settings.session_hours * 3600
    secure = state.settings.cookie_secure
    response.set_cookie(
        SESSION_COOKIE, token, max_age=max_age, httponly=True, secure=secure, samesite="strict", path="/api"
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, max_age=max_age, httponly=False, secure=secure, samesite="strict", path="/"
    )


@router.post("/login", status_code=204)
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    state: AppState = Depends(get_state),
    session: Session = Depends(get_session),
) -> Response:
    ip = client_ip(request)
    limiter = state.login_limiter
    if limiter.is_blocked(ip):
        log_event(logger, "auth.login_blocked", ip=ip)
        raise ApiError(
            429,
            "rate_limited",
            "Troppi tentativi: riprova più tardi",
            {"retry_after_seconds": limiter.retry_after(ip)},
        )
    admin = authenticate(session, payload.email, payload.password)
    if admin is None:
        limiter.hit(ip)
        log_event(logger, "auth.login_failed", ip=ip)
        raise ApiError(401, "invalid_credentials", "Email o password non corrette")
    limiter.reset(ip)
    token = create_session_token(admin.id, state.settings.secret_key, state.settings.session_hours)
    _set_cookies(response, state, token, new_csrf_token())
    log_event(logger, "auth.login", admin=str(admin.id), ip=ip)
    response.status_code = 204
    return response


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(response: Response, admin: AdminUser = Depends(require_admin)) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/api")
    response.delete_cookie(CSRF_COOKIE, path="/")
    log_event(logger, "auth.logout", admin=str(admin.id))
    response.status_code = 204
    return response


@router.get("/me", response_model=AdminOut)
def me(admin: AdminUser = Depends(require_admin)) -> AdminOut:
    return AdminOut(email=admin.email)
