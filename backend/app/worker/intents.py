"""Riconoscimento di richieste semplici che non richiedono il RAG (RF-07, RF-08, RF-17)."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class Intent(StrEnum):
    GREETING = "greeting"
    NON_TEXT = "non_text"
    DELETE_DATA = "delete_data"
    QUESTION = "question"


_GREETINGS = {
    "ciao",
    "salve",
    "buongiorno",
    "buonasera",
    "buon giorno",
    "buona sera",
    "hey",
    "ehi",
    "aiuto",
    "help",
    "menu",
    "info",
    "informazioni",
    "start",
    "inizia",
}
_DELETE = re.compile(r"^\s*cancella\s+(i\s+miei\s+)?dati\s*[.!]?\s*$", re.IGNORECASE)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().strip()
    return re.sub(r"[!?.,;:\s]+", " ", text).strip()


def detect_intent(text: str, kind: str = "text") -> Intent:
    """Classifica il messaggio. Solo i messaggi brevi contano come saluto:
    "ciao, quanto costa Bari–Monopoli?" è una domanda e va al RAG."""
    if kind != "text":
        return Intent.NON_TEXT
    if _DELETE.match(text):
        return Intent.DELETE_DATA
    normalized = _normalize(text)
    if normalized in _GREETINGS or (
        len(normalized.split()) <= 3 and any(normalized.startswith(g) for g in _GREETINGS)
    ):
        return Intent.GREETING
    return Intent.QUESTION


def welcome_message(business_name: str) -> str:
    return (
        f"Ciao! Sono l'assistente virtuale di {business_name} 🚗\n"
        "Rispondo sulle informazioni dei nostri documenti: tariffe, condizioni e servizi.\n\n"
        "Puoi chiedermi ad esempio:\n"
        "• Quanto costa il transfer dall'aeroporto di Bari a Monopoli?\n"
        "• Accettate animali a bordo?\n"
        "• Come posso disdire una prenotazione?"
    )


NON_TEXT_REPLY = "Posso rispondere solo a messaggi scritti: scrivimi la tua domanda e ti aiuto subito."
DELETE_REPLY = "Fatto: ho cancellato i messaggi di questa conversazione. Puoi scrivermi di nuovo quando vuoi."
FAILURE_REPLY = (
    "Al momento non riesco a rispondere. Riprova tra qualche minuto oppure contatta direttamente il titolare."
)
NOT_FOUND_SUFFIX = "\n\nPer questa richiesta ti consiglio di contattare direttamente il titolare."
