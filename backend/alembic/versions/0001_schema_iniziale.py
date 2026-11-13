"""Schema iniziale: 7 tabelle (sezione 4 della specifica).

Revision ID: 0001
Revises:
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("last_login_at", TS),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(255), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("pages", sa.Integer()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("uploaded_at", TS, nullable=False),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_documents_size"),
        sa.CheckConstraint("pages IS NULL OR pages > 0", name="ck_documents_pages"),
        sa.CheckConstraint("status IN ('uploaded','indexed','error')", name="ck_documents_status"),
    )
    op.create_table(
        "index_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("chunks", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("triggered_by", sa.Uuid(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.CheckConstraint("status IN ('queued','running','done','failed')", name="ck_index_jobs_status"),
    )
    op.create_index("ix_index_jobs_status", "index_jobs", ["status"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("contact_hash", sa.String(64)),
        sa.Column("contact_hint", sa.String(16)),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("last_message_at", TS, nullable=False),
        sa.CheckConstraint("channel IN ('web','whatsapp')", name="ck_conversations_channel"),
    )
    op.create_index("ix_conversations_contact", "conversations", ["channel", "contact_hash"])
    op.create_index("ix_conversations_last_message", "conversations", ["last_message_at"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("external_id", sa.String(128), unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("in_reply_to", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="CASCADE")),
        sa.Column("generator", sa.String(16)),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("processing_ms", sa.Integer()),
        sa.Column("created_at", TS, nullable=False),
        sa.CheckConstraint("direction IN ('in','out')", name="ck_messages_direction"),
        sa.CheckConstraint("kind IN ('text','audio','image','location','other')", name="ck_messages_kind"),
        sa.CheckConstraint(
            "status IN ('received','processing','answered','not_found','failed','sent')",
            name="ck_messages_status",
        ),
        sa.CheckConstraint("length(body) <= 4096", name="ck_messages_body_length"),
    )
    op.create_index("ix_messages_conversation", "messages", ["conversation_id", "created_at"])
    op.create_table(
        "message_sources",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.CheckConstraint("rank >= 1", name="ck_message_sources_rank"),
        sa.CheckConstraint("page >= 1", name="ck_message_sources_page"),
        sa.UniqueConstraint("message_id", "rank", name="uq_message_sources_rank"),
    )
    op.create_table(
        "unanswered_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("best_score", sa.Float()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("handled_by", sa.Uuid(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("handled_at", TS),
        sa.CheckConstraint("status IN ('open','handled')", name="ck_unanswered_status"),
    )
    op.create_index("ix_unanswered_status", "unanswered_questions", ["status", "id"])


def downgrade() -> None:
    op.drop_table("unanswered_questions")
    op.drop_table("message_sources")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("index_jobs")
    op.drop_table("documents")
    op.drop_table("admin_users")
