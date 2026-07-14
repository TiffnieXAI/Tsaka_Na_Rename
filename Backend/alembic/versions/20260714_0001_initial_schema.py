"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-14

Mirrors app/models/models.py as of this revision: users, platform_connections,
verification_sessions, risk_assessments, chat_sessions, chat_messages.

NOTE: this was hand-authored (not produced by `alembic revision
--autogenerate`) because no live MySQL instance is reachable from wherever
this was written. Before relying on it:
  1. Point CENTRY_DB_* at a real (empty) MySQL database.
  2. Run `alembic upgrade head`.
  3. Run `alembic check` (or autogenerate a throwaway revision) to confirm
     it matches app/models/models.py exactly - fix either the models or
     this file if they've drifted since.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "platform_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "platform_type",
            sa.Enum("SHOPEE", "LAZADA", "TIKTOK_SHOP", "META", name="platformtype"),
            nullable=False,
        ),
        sa.Column("external_account_id", sa.String(150), nullable=False),
        sa.Column("external_display_name", sa.String(150), nullable=True),
        sa.Column("access_token", sa.String(500), nullable=False),
        sa.Column("refresh_token", sa.String(500), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("CONNECTED", "DISCONNECTED", "EXPIRED", "ERROR", name="connectionstatus"),
            nullable=False,
            server_default="CONNECTED",
        ),
        sa.Column("connected_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "user_id", "platform_type", "external_account_id", name="uq_user_platform"
        ),
    )

    op.create_table(
        "verification_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "COMPLETED", "TERMINATED", name="verificationstatus"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("caller_label", sa.String(150), nullable=True),
        sa.Column("latest_risk_score", sa.Float(), nullable=True),
        sa.Column(
            "latest_risk_level",
            sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risklevel"),
            nullable=True,
        ),
        sa.Column("autonomous_action_taken", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id", sa.Integer(), sa.ForeignKey("verification_sessions.id"), nullable=False
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voice_authenticity_score", sa.Float(), nullable=True),
        sa.Column("voice_model_confidence", sa.Float(), nullable=True),
        sa.Column("semantic_scam_score", sa.Float(), nullable=True),
        sa.Column("detected_scam_markers", sa.JSON(), nullable=True),
        sa.Column("transcript_snippet", sa.Text(), nullable=True),
        sa.Column("aggregated_risk_score", sa.Float(), nullable=False),
        sa.Column(
            "aggregated_risk_level",
            # reuse the same enum type already created for verification_sessions.latest_risk_level
            sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risklevel", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "verification_session_id",
            sa.Integer(),
            sa.ForeignKey("verification_sessions.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "chat_session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id"), nullable=False
        ),
        sa.Column("role", sa.Enum("USER", "ASSISTANT", "SYSTEM", name="chatrole"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("source_incident_ids", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("risk_assessments")
    op.drop_table("verification_sessions")
    op.drop_table("platform_connections")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    # MySQL enums are inline (no catalog type to drop); nothing further needed.
