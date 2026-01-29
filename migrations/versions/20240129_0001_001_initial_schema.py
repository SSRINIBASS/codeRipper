"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create repositories table (using VARCHAR for status to avoid enum issues)
    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("repo_url", sa.String(512), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("owner", sa.String(256), nullable=False),
        sa.Column("primary_language", sa.String(64), nullable=True),
        sa.Column("commit_hash", sa.String(40), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="CREATED"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_files", sa.Integer(), nullable=True),
        sa.Column("total_size_bytes", sa.Integer(), nullable=True),
        sa.Column("total_chunks", sa.Integer(), nullable=True),
        sa.Column("readme_content", sa.Text(), nullable=True),
        sa.Column("architecture_content", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repositories")),
        sa.UniqueConstraint("repo_url", name=op.f("uq_repositories_repo_url")),
    )
    op.create_index(op.f("ix_repositories_repo_url"), "repositories", ["repo_url"])
    op.create_index(op.f("ix_repositories_status"), "repositories", ["status"])

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="1"),
        sa.Column("max_attempts", sa.Integer(), server_default="3"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["repositories.id"],
            name=op.f("fk_jobs_repo_id_repositories"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_jobs_repo_id"), "jobs", ["repo_id"])
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"])

    # Create code_chunks table
    op.create_table(
        "code_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("symbol_type", sa.String(64), nullable=True),
        sa.Column("symbol_name", sa.String(256), nullable=True),
        sa.Column("language", sa.String(64), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding_index", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_code_chunks")),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["repositories.id"],
            name=op.f("fk_code_chunks_repo_id_repositories"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_code_chunks_repo_id"), "code_chunks", ["repo_id"])
    op.create_index(
        op.f("ix_code_chunks_embedding_index"), "code_chunks", ["embedding_index"]
    )

    # Create tutor_sessions table
    op.create_table(
        "tutor_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("repo_context_summary", sa.Text(), nullable=True),
        sa.Column("rolling_conversation_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tutor_sessions")),
        sa.ForeignKeyConstraint(
            ["repo_id"],
            ["repositories.id"],
            name=op.f("fk_tutor_sessions_repo_id_repositories"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_tutor_sessions_repo_id"), "tutor_sessions", ["repo_id"])

    # Create tutor_messages table
    op.create_table(
        "tutor_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("references", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tutor_messages")),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["tutor_sessions.id"],
            name=op.f("fk_tutor_messages_session_id_tutor_sessions"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_tutor_messages_session_id"), "tutor_messages", ["session_id"]
    )

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("key_hash", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_requests", sa.Integer(), server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("key_prefix", name=op.f("uq_api_keys_key_prefix")),
    )
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"])


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("tutor_messages")
    op.drop_table("tutor_sessions")
    op.drop_table("code_chunks")
    op.drop_table("jobs")
    op.drop_table("repositories")
