"""Account admin: creazione all'avvio da variabili d'ambiente (RF-14) e autenticazione."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import MIN_PASSWORD_LENGTH, hash_password, verify_password
from app.db.base import utcnow
from app.db.models import AdminUser

logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def ensure_admin(session: Session, email: str | None, password: str | None) -> AdminUser | None:
    """Crea l'admin se non ne esiste nessuno e le credenziali sono configurate."""
    if session.scalar(select(func.count()).select_from(AdminUser)):
        return None
    if not email or not password:
        logger.warning("Nessun admin: imposta ADMIN_EMAIL e ADMIN_PASSWORD per usare l'area riservata")
        return None
    if len(password) < MIN_PASSWORD_LENGTH:
        logger.error(
            "ADMIN_PASSWORD troppo corta (minimo %d caratteri): admin non creato", MIN_PASSWORD_LENGTH
        )
        return None
    admin = AdminUser(email=normalize_email(email), password_hash=hash_password(password))
    session.add(admin)
    session.flush()
    logger.info("Admin creato")
    return admin


def authenticate(session: Session, email: str, password: str) -> AdminUser | None:
    admin = session.scalar(select(AdminUser).where(AdminUser.email == normalize_email(email)))
    if not verify_password(admin.password_hash if admin else None, password):
        return None
    assert admin is not None
    admin.last_login_at = utcnow()
    return admin


def set_password(session: Session, email: str, password: str) -> bool:
    admin = session.scalar(select(AdminUser).where(AdminUser.email == normalize_email(email)))
    if admin is None:
        return False
    admin.password_hash = hash_password(password)
    return True
