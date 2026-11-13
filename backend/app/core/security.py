"""Funzioni di sicurezza: firma dei webhook Meta e pseudonimizzazione dei numeri (RNF-07)."""

from __future__ import annotations

import hashlib
import hmac
import re

_SIGNATURE_PREFIX = "sha256="


def verify_meta_signature(body: bytes, header: str | None, app_secret: str) -> bool:
    """Verifica ``X-Hub-Signature-256``: HMAC-SHA256 del corpo grezzo con l'App Secret.

    Il confronto è a tempo costante per non rivelare informazioni sulla firma attesa.
    """
    if not header or not header.startswith(_SIGNATURE_PREFIX) or not app_secret:
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix(_SIGNATURE_PREFIX).strip().lower())


def sign_meta_body(body: bytes, app_secret: str) -> str:
    """Calcola l'header di firma come farebbe Meta (usato nei test e negli script di prova)."""
    return _SIGNATURE_PREFIX + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()


def normalize_phone(phone: str) -> str:
    """Solo cifre, senza "+" né spazi: Meta invia i numeri in formato E.164 senza "+"."""
    return re.sub(r"\D", "", phone)


def hash_contact(phone: str, key: str) -> tuple[str, str]:
    """Restituisce (HMAC-SHA256 del numero, ultime 4 cifre).

    Il numero in chiaro non viene mai salvato nel database: l'HMAC con chiave segreta
    permette di ritrovare la conversazione dello stesso numero senza poterlo ricostruire.
    """
    digits = normalize_phone(phone)
    digest = hmac.new(key.encode(), digits.encode(), hashlib.sha256).hexdigest()
    return digest, digits[-4:]
