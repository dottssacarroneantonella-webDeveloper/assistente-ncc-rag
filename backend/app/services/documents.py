"""Documenti PDF della base di conoscenza e caricamento dei documenti di esempio."""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import unicodedata
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Document

logger = logging.getLogger(__name__)
MAX_PDF_BYTES = 10 * 1024 * 1024


def safe_pdf_name(original: str, existing: set[str]) -> str:
    """Nome di file sicuro derivato dall'originale (solo a-z, 0-9, _ e -).

    Il nome resta leggibile perché compare nelle citazioni delle risposte
    (es. ``listino_2026.pdf p.1``), ma non contiene mai percorsi o caratteri speciali.
    """
    stem = Path(original).stem
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^a-z0-9_-]+", "_", stem.lower()).strip("_-")[:80] or "documento"
    name, counter = f"{stem}.pdf", 2
    while name in existing:
        name, counter = f"{stem}_{counter}.pdf", counter + 1
    return name


def count_pages(path: Path) -> int | None:
    try:
        return len(PdfReader(str(path)).pages) or None
    except Exception:  # un PDF illeggibile verrà segnalato dall'indicizzazione
        return None


def register_file(session: Session, source: Path, docs_dir: Path) -> Document | None:
    """Copia un PDF nella cartella dei documenti e lo registra. Restituisce None se è un duplicato."""
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if session.scalar(select(Document.id).where(Document.sha256 == digest)) is not None:
        return None
    docs_dir.mkdir(parents=True, exist_ok=True)
    existing = set(session.scalars(select(Document.stored_name)))
    stored = safe_pdf_name(source.name, existing)
    target = docs_dir / stored
    shutil.copyfile(source, target)
    document = Document(
        original_name=source.name,
        stored_name=stored,
        sha256=digest,
        size_bytes=len(data),
        pages=count_pages(target),
        status="uploaded",
    )
    session.add(document)
    session.flush()
    return document


def count_documents(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Document)) or 0


def seed_example_documents(session: Session, seed_dir: Path, docs_dir: Path) -> int:
    """Carica i PDF di esempio se il database non contiene documenti (RF-14)."""
    if count_documents(session) > 0 or not seed_dir.is_dir():
        return 0
    added = 0
    for pdf in sorted(seed_dir.glob("*.pdf")):
        if register_file(session, pdf, docs_dir) is not None:
            added += 1
    logger.info("Caricati %d documenti di esempio", added)
    return added
