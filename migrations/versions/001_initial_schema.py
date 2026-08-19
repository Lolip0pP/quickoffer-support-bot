"""Initial database schema.

Revision ID: 001
Revises:
Create Date: 2026-08-19 12:39:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tg_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tg_id"),
    )
    op.create_index("idx_conversation_status", "conversations", ["status"])
    op.create_index("idx_conversation_tg_id", "conversations", ["tg_id"])
    op.create_index("idx_conversation_user_id", "conversations", ["user_id"])

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("flow_type", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_support_ticket_conversation_id",
        "support_tickets",
        ["conversation_id"],
    )
    op.create_index(
        "idx_support_ticket_flow_type", "support_tickets", ["flow_type"]
    )
    op.create_index("idx_support_ticket_state", "support_tickets", ["state"])

    op.create_table(
        "support_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("support_ticket_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("frozen_params", sa.JSON(), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "reconciliation_status", sa.String(length=50), nullable=False
        ),
        sa.Column("approval_actor_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["support_ticket_id"],
            ["support_tickets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "idx_support_action_idempotency_key",
        "support_actions",
        ["idempotency_key"],
    )
    op.create_index(
        "idx_support_action_status", "support_actions", ["status"]
    )
    op.create_index(
        "idx_support_action_ticket_id", "support_actions", ["support_ticket_id"]
    )
    op.create_index("idx_support_action_type", "support_actions", ["type"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("support_action_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["support_action_id"],
            ["support_actions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_action", "audit_logs", ["action"])
    op.create_index("idx_audit_log_actor_id", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_log_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_audit_log_target_id", "audit_logs", ["target_id"])


def downgrade() -> None:
    """Downgrade the database."""
    op.drop_table("audit_logs")
    op.drop_table("support_actions")
    op.drop_table("support_tickets")
    op.drop_table("conversations")
