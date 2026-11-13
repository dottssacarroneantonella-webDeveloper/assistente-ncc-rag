"""Configurazione dell'applicazione, letta da variabili d'ambiente e dal file .env.

Nessun segreto è scritto nel codice: i valori predefiniti funzionano solo in locale
e per la demo, dove non ci sono dati reali.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
DEV_ONLY_SECRET = "solo-per-sviluppo-cambiami"  # noqa: S105 - segnaposto rifiutato in produzione


class Settings(BaseSettings):
    """Parametri dell'applicazione (prefisso nessuno, nomi come in .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "demo", "production"] = "development"
    business_name: str = "NCC Levante Transfer"

    # Database: SQLite per demo e test, PostgreSQL con Docker Compose
    database_url: str = "sqlite:///./data/app.db"
    auto_create_schema: bool = True  # in produzione si usano le migrazioni Alembic

    # Coda: "memory" (un solo processo, demo e test) oppure "rabbitmq"
    queue_backend: Literal["memory", "rabbitmq"] = "memory"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_base_seconds: float = Field(default=2.0, ge=0)

    # RAG
    answer_generator: Literal["extractive", "ollama", "openai"] = "extractive"
    rag_embedder: Literal["tfidf", "sentence-transformers"] = "tfidf"
    rag_store: Literal["numpy", "faiss"] = "numpy"
    rag_top_k: int = Field(default=4, ge=1, le=20)
    rag_min_score: float | None = None
    rag_index_dir: Path = Path("data/index")
    docs_dir: Path = Path("data/docs")
    seed_docs_dir: Path = PROJECT_DIR / "examples" / "ncc-docs"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None

    # Chat web
    frontend_origin: str = "http://localhost:5173"
    max_question_chars: int = Field(default=1000, ge=10, le=4096)

    # Privacy
    retention_days: int = Field(default=30, ge=1)
    retention_interval_hours: float = Field(default=24, gt=0)

    # Limiti della chat web per IP (RNF / sezione 7)
    chat_messages_per_minute: int = Field(default=10, ge=1)
    chat_messages_per_day: int = Field(default=100, ge=1)
    chat_conversations_per_hour: int = Field(default=30, ge=1)
    contact_hash_key: str = DEV_ONLY_SECRET  # in produzione: valore casuale lungo

    # WhatsApp (Meta Cloud API) – attivo solo se WHATSAPP_ENABLED=true e i valori sono presenti
    whatsapp_enabled: bool = False
    meta_access_token: str | None = None
    meta_phone_number_id: str | None = None
    meta_app_secret: str | None = None
    meta_verify_token: str | None = None
    meta_graph_version: str = "v21.0"
    meta_graph_base_url: str = "https://graph.facebook.com"
    meta_timeout_seconds: float = Field(default=10.0, gt=0)

    # Area admin
    # firma dei JWT: in produzione valore casuale lungo (l'avvio fallisce con il valore predefinito)
    secret_key: str = DEV_ONLY_SECRET
    admin_email: str | None = None
    admin_password: str | None = None
    session_hours: int = Field(default=8, ge=1, le=24)
    login_max_attempts: int = Field(default=5, ge=1)
    login_window_minutes: int = Field(default=15, ge=1)
    max_upload_mb: int = Field(default=10, ge=1, le=50)

    # Worker
    worker_prefetch: int = Field(default=4, ge=1, le=100)
    queue_prefix: str = "ncc"

    @field_validator(
        "openai_api_key",
        "rag_min_score",
        "meta_access_token",
        "meta_phone_number_id",
        "meta_app_secret",
        "meta_verify_token",
        "admin_email",
        "admin_password",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _no_placeholder_secrets_in_production(self) -> Settings:
        if self.app_env in ("production", "demo"):
            weak = [
                name
                for name in ("secret_key", "contact_hash_key")
                if getattr(self, name) == DEV_ONLY_SECRET or len(getattr(self, name)) < 32
            ]
            if weak:
                names = ", ".join(n.upper() for n in weak)
                raise ValueError(
                    f"In {self.app_env} imposta un valore casuale di almeno 32 caratteri per {names}"
                )
        return self

    @property
    def whatsapp_configured(self) -> bool:
        """True se WhatsApp è attivo e tutte le credenziali Meta sono presenti."""
        return self.whatsapp_enabled and all(
            (
                self.meta_access_token,
                self.meta_phone_number_id,
                self.meta_app_secret,
                self.meta_verify_token,
            )
        )

    @property
    def cookie_secure(self) -> bool:
        """Cookie solo su HTTPS, tranne in sviluppo e nei test (http://localhost)."""
        return self.app_env not in ("development", "test")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Restituisce le impostazioni (una sola istanza per processo)."""
    return Settings()
