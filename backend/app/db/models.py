"""Modelli del database (sezione 4 della specifica)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class UTCDateTime(TypeDecorator[datetime]):
    """Data e ora sempre in UTC, anche su SQLite (che non conserva il fuso orario)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


ID = BigInteger().with_variant(Integer, "sqlite")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_documents_size"),
        CheckConstraint("pages IS NULL OR pages > 0", name="ck_documents_pages"),
        CheckConstraint("status IN ('uploaded','indexed','error')", name="ck_documents_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class IndexJob(Base):
    __tablename__ = "index_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','done','failed')", name="ck_index_jobs_status"),
        Index("ix_index_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    chunks: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("channel IN ('web','whatsapp')", name="ck_conversations_channel"),
        Index("ix_conversations_contact", "channel", "contact_hash"),
        Index("ix_conversations_last_message", "last_message_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(String(16))
    contact_hash: Mapped[str | None] = mapped_column(String(64))
    contact_hint: Mapped[str | None] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_message_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("direction IN ('in','out')", name="ck_messages_direction"),
        CheckConstraint("kind IN ('text','audio','image','location','other')", name="ck_messages_kind"),
        CheckConstraint(
            "status IN ('received','processing','answered','not_found','failed','sent')",
            name="ck_messages_status",
        ),
        CheckConstraint("length(body) <= 4096", name="ck_messages_body_length"),
        Index("ix_messages_conversation", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE")
    )
    direction: Mapped[str] = mapped_column(String(8))
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    kind: Mapped[str] = mapped_column(String(16), default="text")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    in_reply_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("messages.id", ondelete="CASCADE"))
    generator: Mapped[str | None] = mapped_column(String(16))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sources: Mapped[list[MessageSource]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="MessageSource.rank"
    )


class MessageSource(Base):
    __tablename__ = "message_sources"
    __table_args__ = (
        CheckConstraint("rank >= 1", name="ck_message_sources_rank"),
        CheckConstraint("page >= 1", name="ck_message_sources_page"),
        UniqueConstraint("message_id", "rank", name="uq_message_sources_rank"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("messages.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(SmallInteger)
    source_file: Mapped[str] = mapped_column(String(255))
    page: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    excerpt: Mapped[str] = mapped_column(Text)


class UnansweredQuestion(Base):
    __tablename__ = "unanswered_questions"
    __table_args__ = (
        CheckConstraint("status IN ('open','handled')", name="ck_unanswered_status"),
        Index("ix_unanswered_status", "status", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    best_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="open")
    note: Mapped[str | None] = mapped_column(String(500))
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    message: Mapped[Message] = relationship()
