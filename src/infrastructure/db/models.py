"""SQLAlchemy ORM models for the support bot."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Conversation(Base):
    """Telegram conversation model."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, closed, suspended
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    support_tickets: Mapped[list["SupportTicket"]] = relationship(
        "SupportTicket", back_populates="conversation"
    )

    __table_args__ = (
        Index("idx_conversation_tg_id", "tg_id"),
        Index("idx_conversation_user_id", "user_id"),
        Index("idx_conversation_status", "status"),
    )


class SupportTicket(Base):
    """Support ticket model."""

    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    flow_type: Mapped[str] = mapped_column(
        String(100)
    )  # e.g., "issue_resolution", "feature_request"
    state: Mapped[str] = mapped_column(
        String(100)
    )  # e.g., "pending", "in_progress", "resolved"
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="support_tickets"
    )
    support_actions: Mapped[list["SupportAction"]] = relationship(
        "SupportAction", back_populates="support_ticket"
    )

    __table_args__ = (
        Index("idx_support_ticket_conversation_id", "conversation_id"),
        Index("idx_support_ticket_flow_type", "flow_type"),
        Index("idx_support_ticket_state", "state"),
    )


class SupportAction(Base):
    """Support action model - represents mutations with approval tracking."""

    __tablename__ = "support_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    support_ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(100)
    )  # e.g., "escalate", "reassign", "resolve"
    risk_level: Mapped[str] = mapped_column(
        String(50)
    )  # "low", "medium", "high", "critical"
    frozen_params: Mapped[dict[str, Any]] = mapped_column(
        JSON
    )  # Immutable action parameters
    params_hash: Mapped[str] = mapped_column(
        String(64)
    )  # SHA256 hash of frozen_params
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, approved, rejected, executed
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )  # UUID for M2M idempotency
    reconciliation_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, confirmed, failed, retrying
    approval_actor_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    support_ticket: Mapped[SupportTicket] = relationship(
        "SupportTicket", back_populates="support_actions"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="support_action"
    )

    __table_args__ = (
        Index("idx_support_action_ticket_id", "support_ticket_id"),
        Index("idx_support_action_type", "type"),
        Index("idx_support_action_status", "status"),
        Index("idx_support_action_idempotency_key", "idempotency_key"),
    )


class AuditLog(Base):
    """Audit log for tracking all mutations."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    support_action_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("support_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(String(255), index=True)
    target_id: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(100))  # created, updated, deleted
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    support_action: Mapped[SupportAction | None] = relationship(
        "SupportAction", back_populates="audit_logs"
    )

    __table_args__ = (
        Index("idx_audit_log_actor_id", "actor_id"),
        Index("idx_audit_log_target_id", "target_id"),
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_created_at", "created_at"),
    )


class ReferralOwnershipMapping(Base):
    """Mapping between QuickOffer user and their referral promo code."""

    __tablename__ = "referral_ownership_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )  # QuickOffer user ID
    promo_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True
    )  # Generated 15% referral code
    discount_percent: Mapped[int] = mapped_column(
        default=15
    )  # Always 15% for referral
    is_active: Mapped[bool] = mapped_column(
        default=True, index=True
    )  # Whether code is active
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_referral_mapping_user_id", "user_id"),
        Index("idx_referral_mapping_promo_code", "promo_code"),
        Index("idx_referral_mapping_is_active", "is_active"),
    )


class ReviewPromoCodeUsage(Base):
    """One-time promo code issued for review submission."""

    __tablename__ = "review_promo_code_usages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String(255), index=True
    )  # QuickOffer user ID
    review_id: Mapped[str] = mapped_column(
        String(255), index=True
    )  # Review ID from fuckhr
    promo_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True
    )  # One-time 15% code
    discount_percent: Mapped[int] = mapped_column(
        default=15
    )  # Always 15% for review
    max_uses: Mapped[int] = mapped_column(default=1)  # One-time use only
    times_used: Mapped[int] = mapped_column(default=0)  # Usage counter
    is_active: Mapped[bool] = mapped_column(
        default=True, index=True
    )  # Whether code is usable
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_review_promo_user_id", "user_id"),
        Index("idx_review_promo_review_id", "review_id"),
        Index("idx_review_promo_code", "promo_code"),
        Index("idx_review_promo_is_active", "is_active"),
    )


class KnowledgeBaseVersion(Base):
    """Knowledge base version with ownership and lifecycle metadata."""

    __tablename__ = "knowledge_base_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[str] = mapped_column(String(255), index=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(50), default="active", index=True
    )  # active, draft, archived
    content_hash: Mapped[str] = mapped_column(String(64))
    effective_date: Mapped[datetime] = mapped_column(
        DateTime, index=True
    )
    review_date: Mapped[datetime] = mapped_column(
        DateTime, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_kb_version_kb_id", "kb_id"),
        Index("idx_kb_version_owner", "owner"),
        Index("idx_kb_version_status", "status"),
        Index("idx_kb_version_effective_date", "effective_date"),
        Index("idx_kb_version_review_date", "review_date"),
    )


class HandoffTicket(Base):
    """Handoff ticket for escalation to human support."""

    __tablename__ = "handoff_tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    trigger_type: Mapped[str] = mapped_column(
        String(100), index=True
    )  # explicit_request, identity_not_verified, etc.
    trigger_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(50), default="created", index=True
    )  # created, notified, assigned, in_progress, resolved, escalated
    investigation_summary: Mapped[str] = mapped_column(Text, default="")
    confidence_score: Mapped[float] = mapped_column(default=0.0)
    assigned_to: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation", backref="handoff_tickets"
    )
    collected_facts: Mapped[list["CollectedFact"]] = relationship(
        "CollectedFact", back_populates="handoff_ticket"
    )

    __table_args__ = (
        Index("idx_handoff_ticket_conversation_id", "conversation_id"),
        Index("idx_handoff_ticket_user_id", "user_id"),
        Index("idx_handoff_ticket_trigger_type", "trigger_type"),
        Index("idx_handoff_ticket_status", "status"),
        Index("idx_handoff_ticket_assigned_to", "assigned_to"),
    )


class CollectedFact(Base):
    """Fact collected during investigation before handoff."""

    __tablename__ = "collected_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    handoff_ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("handoff_tickets.id", ondelete="CASCADE"),
        index=True,
    )
    fact_type: Mapped[str] = mapped_column(
        String(100)
    )  # user_message, tool_failure, llm_error, etc.
    source: Mapped[str] = mapped_column(
        String(100)
    )  # user_input, investigation_service, llm_service, system
    value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    handoff_ticket: Mapped[HandoffTicket] = relationship(
        "HandoffTicket", back_populates="collected_facts"
    )

    __table_args__ = (
        Index("idx_collected_fact_ticket_id", "handoff_ticket_id"),
        Index("idx_collected_fact_type", "fact_type"),
        Index("idx_collected_fact_source", "source"),
    )
