"""Adattatore verso la libreria rag-pdf-qa.

Il resto dell'applicazione non conosce i dettagli del RAG: chiede ``answer(domanda)`` e
``rebuild(cartella)``. La reindicizzazione costruisce il nuovo indice in una cartella
temporanea e lo sostituisce con un rename, così le domande in arrivo non vedono mai un
indice a metà (questione aperta n. 5 della specifica).
"""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from rag_pdf_qa.config import Settings as RagSettings
from rag_pdf_qa.llm import LLMError
from rag_pdf_qa.pipeline import RagPipeline

from app.core.config import Settings
from app.queue.base import TransientError

logger = logging.getLogger(__name__)

# Nome del generatore in configurazione → nome dell'LLM in rag-pdf-qa
_GENERATORS = {"extractive": "echo", "ollama": "ollama", "openai": "openai"}


@dataclass(frozen=True)
class SourceRef:
    """Fonte citata in una risposta."""

    file: str
    page: int
    score: float
    excerpt: str


@dataclass(frozen=True)
class RagAnswer:
    text: str
    answered: bool
    generator: str
    sources: list[SourceRef] = field(default_factory=list)

    @property
    def best_score(self) -> float | None:
        return max((s.score for s in self.sources), default=None)


@dataclass(frozen=True)
class RebuildReport:
    documents: int
    pages: int
    chunks: int


class IndexNotReadyError(TransientError):
    """L'indice non esiste ancora (prima indicizzazione in corso)."""


class RagEngine:
    """Motore RAG condiviso tra le richieste; sicuro rispetto ai thread."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.index_dir = Path(settings.rag_index_dir)
        self._lock = threading.Lock()
        self._pipeline: RagPipeline | None = None

    def _rag_settings(self, index_dir: Path) -> RagSettings:
        s = self.settings
        return RagSettings(
            index_dir=index_dir,
            embedder=s.rag_embedder,
            store=s.rag_store,
            llm=_GENERATORS[s.answer_generator],
            ollama_model=s.ollama_model,
            ollama_url=s.ollama_url,
            openai_base_url=s.openai_base_url,
            openai_model=s.openai_model,
            openai_api_key=s.openai_api_key,
            top_k=s.rag_top_k,
            min_score=s.rag_min_score,
        )

    @property
    def is_ready(self) -> bool:
        return (self.index_dir / "manifest.json").exists()

    def rebuild(self, docs_dir: Path) -> RebuildReport:
        """Ricostruisce l'indice dai PDF di ``docs_dir`` e lo sostituisce in modo atomico."""
        self.index_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.index_dir.with_name(f"{self.index_dir.name}.tmp-{uuid.uuid4().hex[:8]}")
        try:
            report = RagPipeline(self._rag_settings(tmp)).ingest(docs_dir)
            with self._lock:
                old = self.index_dir.with_name(f"{self.index_dir.name}.old")
                if self.index_dir.exists():
                    shutil.rmtree(old, ignore_errors=True)
                    self.index_dir.rename(old)
                tmp.rename(self.index_dir)
                shutil.rmtree(old, ignore_errors=True)
                self._pipeline = None  # la prossima domanda ricarica il nuovo indice
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return RebuildReport(documents=report.documents, pages=report.pages, chunks=report.chunks)

    def _get_pipeline(self) -> RagPipeline:
        with self._lock:
            if self._pipeline is None:
                if not self.is_ready:
                    raise IndexNotReadyError("Indice non ancora disponibile")
                self._pipeline = RagPipeline(self._rag_settings(self.index_dir))
            return self._pipeline

    def answer(self, question: str) -> RagAnswer:
        """Risponde usando solo i documenti indicizzati.

        Un LLM non raggiungibile diventa ``TransientError``, così la coda ritenta.
        """
        pipeline = self._get_pipeline()
        try:
            result = pipeline.ask(question)
        except LLMError as exc:
            raise TransientError(str(exc)) from exc
        sources = [
            SourceRef(file=r.chunk.source, page=r.chunk.page, score=round(r.score, 4), excerpt=r.chunk.text)
            for r in result.sources
        ]
        return RagAnswer(
            text=result.text,
            answered=result.answered,
            generator=self.settings.answer_generator,
            sources=sources,
        )
