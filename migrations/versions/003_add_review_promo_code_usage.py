"""Add review promo code usage table.

Revision ID: 003
Revises: 002
Create Date: 2026-08-19 12:57:15.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade the database."""
    op.create_table(
        "review_promo_code_usages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("review_id", sa.String(length=255), nullable=False),
        sa.Column("promo_code", sa.String(length=50), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("times_used", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promo_code"),
    )
    op.create_index(
        "idx_review_promo_user_id",
        "review_promo_code_usages",
        ["user_id"],
    )
    op.create_index(
        "idx_review_promo_review_id",
        "review_promo_code_usages",
        ["review_id"],
    )
    op.create_index(
        "idx_review_promo_code",
        "review_promo_code_usages",
        ["promo_code"],
    )
    op.create_index(
        "idx_review_promo_is_active",
        "review_promo_code_usages",
        ["is_active"],
    )


def downgrade() -> None:
    """Downgrade the database."""
    op.drop_table("review_promo_code_usages")
