"""Domain entities - value objects and DTOs for business logic."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ConversationStatus(str, Enum):
    """Conversation status enumeration."""

    ACTIVE = "active"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class SupportTicketState(str, Enum):
    """Support ticket state enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REOPENED = "reopened"


class SupportActionType(str, Enum):
    """Support action type enumeration."""

    ESCALATE = "escalate"
    REASSIGN = "reassign"
    RESOLVE = "resolve"
    UPDATE_METADATA = "update_metadata"


class RiskLevel(str, Enum):
    """Risk level enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SupportActionStatus(str, Enum):
    """Support action status enumeration."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class ReconciliationStatus(str, Enum):
    """Reconciliation status enumeration."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ConversationEntity:
    """Domain entity for Conversation."""

    tg_id: int
    user_id: str
    status: ConversationStatus = ConversationStatus.ACTIVE
    id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class SupportTicketEntity:
    """Domain entity for SupportTicket."""

    conversation_id: uuid.UUID
    flow_type: str
    state: SupportTicketState
    metadata: dict[str, Any] | None = None
    id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class FrozenParams:
    """Immutable action parameters."""

    action_type: SupportActionType
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_type": self.action_type.value,
            "data": self.data,
        }


@dataclass
class SupportActionEntity:
    """Domain entity for SupportAction."""

    support_ticket_id: uuid.UUID
    action_type: SupportActionType
    risk_level: RiskLevel
    frozen_params: FrozenParams
    params_hash: str
    idempotency_key: str
    id: uuid.UUID | None = None
    status: SupportActionStatus = SupportActionStatus.PENDING
    reconciliation_status: ReconciliationStatus = (
        ReconciliationStatus.PENDING
    )
    approval_actor_id: str | None = None
    created_at: datetime | None = None
    approved_at: datetime | None = None
    executed_at: datetime | None = None


@dataclass
class AuditLogEntity:
    """Domain entity for AuditLog."""

    actor_id: str
    target_id: str
    action: str
    payload: dict[str, Any]
    support_action_id: uuid.UUID | None = None
    id: uuid.UUID | None = None
    created_at: datetime | None = None


@dataclass
class ReferralPromoCodeResponse:
    """Response from referral promo code request."""

    code: str
    discount_percent: int
    expires_at: str | None
    is_new: bool


@dataclass
class ReviewCheckResponse:
    """Response from review check request."""

    review_found: bool
    review_id: str | None
    review_text: str | None
    review_length: int | None


@dataclass
class ReviewPromoCodeResponse:
    """Response from review promo code request."""

    code: str
    discount_percent: int
    max_uses: int
    user_bound: bool
    is_new: bool
    review_id: str | None
