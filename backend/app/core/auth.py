"""Password (Argon2id) e token di sessione (JWT HS256) per l'area admin."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # parametri di default della libreria: Argon2id
_ALGORITHM = "HS256"
_AUDIENCE = "assistente-ncc-admin"
MIN_PASSWORD_LENGTH = 12

# hash di riserva: si verifica comunque una password anche se l'email non esiste,
# così il tempo di risposta non rivela quali email sono registrate
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"La password deve avere almeno {MIN_PASSWORD_LENGTH} caratteri")
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_session_token(admin_id: uuid.UUID, secret: str, hours: int) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(admin_id),
        "aud": _AUDIENCE,
        "iat": now,
        "exp": now + timedelta(hours=hours),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)


def read_session_token(token: str, secret: str) -> uuid.UUID | None:
    """Restituisce l'ID dell'admin se il token è valido e non scaduto, altrimenti None."""
    try:
        claims = jwt.decode(token, secret, algorithms=[_ALGORITHM], audience=_AUDIENCE)
        return uuid.UUID(str(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
