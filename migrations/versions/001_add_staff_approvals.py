"""Add staff approvals and enhanced tracking tables.

Revision ID: 001_add_staff_approvals
Revises:
Create Date: 2026-08-19 13:23:34.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_add_staff_approvals"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema for staff approvals."""
    # Create staff_allowlist table
    op.create_table(
        "staff_allowlist",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("staff_id", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("roles", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_staff_allowlist_staff_id", "staff_id"),
        sa.Index("idx_staff_allowlist_is_active", "is_active"),
    )

    # Add additional columns to support_actions table for approval tracking
    op.add_column(
        "support_actions",
        sa.Column("approval_request_sent_at", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "support_actions",
        sa.Column("approval_message_id", sa.Integer(), nullable=True),
    )

    # Create approval_decisions table
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("action_id", sa.UUID(), nullable=False),
        sa.Column("staff_id", sa.String(255), nullable=False),
        sa.Column("decision", sa.String(50), nullable=False),  # approved, rejected
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["support_actions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_approval_decision_action_id", "action_id"),
        sa.Index("idx_approval_decision_staff_id", "staff_id"),
    )

    # Create approval_info_requests table (for info requests)
    op.create_table(
        "approval_info_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("action_id", sa.UUID(), nullable=False),
        sa.Column("staff_id", sa.String(255), nullable=False),
        sa.Column("info_request", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["support_actions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_approval_info_request_action_id", "action_id"),
        sa.Index("idx_approval_info_request_staff_id", "staff_id"),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table("approval_info_requests")
    op.drop_table("approval_decisions")
    op.drop_column("support_actions", "approval_message_id")
    op.drop_column("support_actions", "approval_request_sent_at")
    op.drop_table("staff_allowlist")
