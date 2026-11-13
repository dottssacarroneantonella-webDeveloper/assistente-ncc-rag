"""Schemi Pydantic delle richieste e delle risposte API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: bool
    queue: bool
    index_ready: bool


class ConversationOut(BaseModel):
    id: uuid.UUID
    welcome: str


class MessageIn(BaseModel):
    text: str = Field(min_length=1)


class MessageAccepted(BaseModel):
    message_id: uuid.UUID


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    file: str
    page: int
    score: float
    excerpt: str


class MessageOut(BaseModel):
    id: uuid.UUID
    direction: Literal["in", "out"]
    body: str
    status: str
    in_reply_to: uuid.UUID | None
    sources: list[SourceOut]
    created_at: datetime


class MessagesOut(BaseModel):
    items: list[MessageOut]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] | list[object] | None = None


class ErrorOut(BaseModel):
    error: ErrorBody


# --- area admin -----------------------------------------------------------------------------


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class AdminOut(BaseModel):
    email: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_name: str
    stored_name: str
    size_bytes: int
    pages: int | None
    status: str
    uploaded_at: datetime


class DocumentsOut(BaseModel):
    items: list[DocumentOut]


class IndexJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    chunks: int | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class IndexJobsOut(BaseModel):
    items: list[IndexJobOut]


class ConversationSummary(BaseModel):
    id: uuid.UUID
    channel: str
    contact: str | None
    messages: int
    started_at: datetime
    last_message_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class AdminMessageOut(MessageOut):
    kind: str
    generator: str | None
    processing_ms: int | None


class ConversationDetail(BaseModel):
    conversation: ConversationSummary
    messages: list[AdminMessageOut]


class UnansweredOut(BaseModel):
    id: uuid.UUID
    question: str
    conversation_id: uuid.UUID
    asked_at: datetime
    best_score: float | None
    status: Literal["open", "handled"]
    note: str | None
    handled_at: datetime | None


class UnansweredPatch(BaseModel):
    status: Literal["open", "handled"]
    note: str | None = Field(default=None, max_length=500)
