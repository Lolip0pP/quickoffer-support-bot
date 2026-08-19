"""Add Mode B (LLM Investigation) and Handoff tables.

Revision ID: 003
Revises:
Create date: 2024-08-19 13:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Mode B and Handoff tables."""
    # Create KnowledgeBaseVersion table
    op.create_table(
        "knowledge_base_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.String(255), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("effective_date", sa.DateTime(), nullable=False),
        sa.Column("review_date", sa.DateTime(), nullable=False),
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
    )
    op.create_index("idx_kb_version_kb_id", "knowledge_base_versions", ["kb_id"])
    op.create_index("idx_kb_version_owner", "knowledge_base_versions", ["owner"])
    op.create_index("idx_kb_version_status", "knowledge_base_versions", ["status"])
    op.create_index(
        "idx_kb_version_effective_date",
        "knowledge_base_versions",
        ["effective_date"],
    )
    op.create_index(
        "idx_kb_version_review_date",
        "knowledge_base_versions",
        ["review_date"],
    )

    # Create HandoffTicket table
    op.create_table(
        "handoff_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("trigger_type", sa.String(100), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="created"
        ),
        sa.Column("investigation_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_handoff_ticket_conversation_id",
        "handoff_tickets",
        ["conversation_id"],
    )
    op.create_index("idx_handoff_ticket_user_id", "handoff_tickets", ["user_id"])
    op.create_index(
        "idx_handoff_ticket_trigger_type",
        "handoff_tickets",
        ["trigger_type"],
    )
    op.create_index("idx_handoff_ticket_status", "handoff_tickets", ["status"])
    op.create_index(
        "idx_handoff_ticket_assigned_to",
        "handoff_tickets",
        ["assigned_to"],
    )

    # Create CollectedFact table
    op.create_table(
        "collected_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("handoff_ticket_id", sa.Uuid(), nullable=False),
        sa.Column("fact_type", sa.String(100), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["handoff_ticket_id"], ["handoff_tickets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_collected_fact_ticket_id",
        "collected_facts",
        ["handoff_ticket_id"],
    )
    op.create_index("idx_collected_fact_type", "collected_facts", ["fact_type"])
    op.create_index("idx_collected_fact_source", "collected_facts", ["source"])


def downgrade() -> None:
    """Drop Mode B and Handoff tables."""
    op.drop_index("idx_collected_fact_source", table_name="collected_facts")
    op.drop_index("idx_collected_fact_type", table_name="collected_facts")
    op.drop_index("idx_collected_fact_ticket_id", table_name="collected_facts")
    op.drop_table("collected_facts")

    op.drop_index("idx_handoff_ticket_assigned_to", table_name="handoff_tickets")
    op.drop_index("idx_handoff_ticket_status", table_name="handoff_tickets")
    op.drop_index("idx_handoff_ticket_trigger_type", table_name="handoff_tickets")
    op.drop_index("idx_handoff_ticket_user_id", table_name="handoff_tickets")
    op.drop_index(
        "idx_handoff_ticket_conversation_id", table_name="handoff_tickets"
    )
    op.drop_table("handoff_tickets")

    op.drop_index("idx_kb_version_review_date", table_name="knowledge_base_versions")
    op.drop_index(
        "idx_kb_version_effective_date", table_name="knowledge_base_versions"
    )
    op.drop_index("idx_kb_version_status", table_name="knowledge_base_versions")
    op.drop_index("idx_kb_version_owner", table_name="knowledge_base_versions")
    op.drop_index("idx_kb_version_kb_id", table_name="knowledge_base_versions")
    op.drop_table("knowledge_base_versions")
