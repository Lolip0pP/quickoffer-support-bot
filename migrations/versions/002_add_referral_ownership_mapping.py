"""Add referral ownership mapping table.

Revision ID: 002
Revises: 001
Create Date: 2026-08-19 12:57:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    op.create_table(
        "referral_ownership_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("promo_code", sa.String(length=50), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("promo_code"),
    )
    op.create_index(
        "idx_referral_mapping_user_id",
        "referral_ownership_mappings",
        ["user_id"],
    )
    op.create_index(
        "idx_referral_mapping_promo_code",
        "referral_ownership_mappings",
        ["promo_code"],
    )
    op.create_index(
        "idx_referral_mapping_is_active",
        "referral_ownership_mappings",
        ["is_active"],
    )


def downgrade() -> None:
    """Downgrade the database."""
    op.drop_table("referral_ownership_mappings")
