"""Schemi Pydantic delle richieste e delle risposte API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

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
