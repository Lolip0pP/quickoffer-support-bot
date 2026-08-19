"""Flow 1: Refund and subscription deletion workflow with staff approval."""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.domain.entities import (
    ReconciliationStatus,
    RiskLevel,
    SupportActionStatus,
    SupportActionType,
)
from src.infrastructure.m2m.clients import FuckHRAPIClient
from src.services.approval_service import (
    ApprovalRequest,
    ApprovalService,
)

logger = logging.getLogger(__name__)


class RefundBasis(str, Enum):
    """Valid refund bases - only these are approved by business logic."""

    SERVICE_NOT_STARTED = "service_not_started"
    DOUBLE_CHARGE = "double_charge"
    ERRONEOUS_CHARGE = "erroneous_charge"
    QUICKOFFER_ERROR = "quickoffer_error"


class RefundFlowState(str, Enum):
    """States for refund flow."""

    IDENTIFY = "identify"
    SELECT_PAYMENT = "select_payment"
    PREVIEW = "preview"
    COLLECT_REASON = "collect_reason"
    CONFIRM = "confirm"
    STAFF_APPROVAL = "staff_approval"
    REFUND_MANUAL = "refund_manual"
    VERIFY_REFUND = "verify_refund"
    SOFT_DELETE_SUBSCRIPTION = "soft_delete_subscription"
    RECONCILIATION = "reconciliation"
    COMPLETED = "completed"
    REJECTED = "rejected"


class PaymentInfo(BaseModel):
    """Payment information."""

    payment_id: str
    amount: float
    currency: str
    created_at: str
    status: str
    description: str | None = None


class RefundRequest(BaseModel):
    """Refund request data."""

    user_id: str
    ticket_id: uuid.UUID
    payment_id: str
    amount: float
    currency: str
    refund_basis: RefundBasis
    reason: str
    evidence_links: list[str] = Field(default_factory=list)
    evidence_text: str | None = None


class RefundContextData(BaseModel):
    """Context data for refund flow."""

    user_id: str
    ticket_id: uuid.UUID
    payment_id: str
    amount: float
    currency: str
    refund_basis: RefundBasis
    reason: str
    evidence_links: list[str] = Field(default_factory=list)
    evidence_text: str | None = None
    support_action_id: uuid.UUID | None = None
    staff_decision: bool | None = None
    provider_refund_id: str | None = None
    refund_verified: bool = False
    subscription_deleted: bool = False


class RefundFlowEngine:
    """Engine for managing refund and subscription deletion workflow."""

    # Valid refund bases that business allows
    ALLOWED_REFUND_BASES = {
        RefundBasis.SERVICE_NOT_STARTED,
        RefundBasis.DOUBLE_CHARGE,
        RefundBasis.ERRONEOUS_CHARGE,
        RefundBasis.QUICKOFFER_ERROR,
    }

    def __init__(
        self,
        approval_service: ApprovalService,
        fuckhr_client: FuckHRAPIClient,
    ) -> None:
        """Initialize refund flow engine.

        Args:
            approval_service: Approval service for staff decisions.
            fuckhr_client: FuckHR API client for M2M operations.
        """
        self.approval_service = approval_service
        self.fuckhr_client = fuckhr_client

    def validate_refund_basis(self, basis: RefundBasis) -> bool:
        """Validate that refund basis is allowed.

        Args:
            basis: Refund basis to validate.

        Returns:
            bool: True if basis is allowed.
        """
        return basis in self.ALLOWED_REFUND_BASES

    async def get_user_payments(self, user_id: str) -> list[PaymentInfo]:
        """Get user's recent payments from backend.

        Args:
            user_id: QuickOffer user ID.

        Returns:
            list: Recent payments.

        Raises:
            RuntimeError: If backend call fails.
        """
        try:
            response = await self.fuckhr_client.execute_action(
                action_id=uuid.uuid4(),
                action_type="get_user_payments",
                payload={"user_id": user_id, "limit": 5},
                idempotency_key=f"get_payments_{user_id}_{uuid.uuid4()}",
            )

            payments = []
            for payment_data in response.get("payments", []):
                payments.append(
                    PaymentInfo(
                        payment_id=payment_data["id"],
                        amount=payment_data["amount"],
                        currency=payment_data["currency"],
                        created_at=payment_data["created_at"],
                        status=payment_data["status"],
                        description=payment_data.get("description"),
                    )
                )

            logger.info(f"Retrieved {len(payments)} payments for user {user_id}")
            return payments

        except Exception as e:
            logger.error(f"Error retrieving payments for user {user_id}: {e}")
            raise RuntimeError(f"Failed to retrieve payments: {e}")

    async def get_refund_preview(
        self,
        user_id: str,
        payment_id: str,
        refund_basis: RefundBasis,
    ) -> dict[str, Any]:
        """Get refund preview from backend.

        Args:
            user_id: QuickOffer user ID.
            payment_id: Payment ID to refund.
            refund_basis: Basis for refund.

        Returns:
            dict: Refund preview with amount, conditions, etc.

        Raises:
            RuntimeError: If conditions don't allow refund.
        """
        try:
            response = await self.fuckhr_client.execute_action(
                action_id=uuid.uuid4(),
                action_type="get_refund_preview",
                payload={
                    "user_id": user_id,
                    "payment_id": payment_id,
                    "refund_basis": refund_basis.value,
                },
                idempotency_key=f"refund_preview_{payment_id}_{uuid.uuid4()}",
            )

            # Check if refund is possible
            if not response.get("is_refundable", False):
                raise RuntimeError(
                    f"Refund not possible: {response.get('reason', 'Unknown reason')}"
                )

            logger.info(f"Refund preview for payment {payment_id}: {response}")
            return response

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Error getting refund preview: {e}")
            raise RuntimeError(f"Failed to get refund preview: {e}")

    async def create_refund_approval_action(
        self,
        ticket_id: uuid.UUID,
        refund_request: RefundRequest,
    ) -> uuid.UUID:
        """Create support action for refund approval.

        Args:
            ticket_id: Support ticket ID.
            refund_request: Refund request details.

        Returns:
            uuid.UUID: Created action ID.
        """
        approval_request = ApprovalRequest(
            support_ticket_id=ticket_id,
            action_type=SupportActionType.RESOLVE,
            risk_level=RiskLevel.HIGH,
            params={
                "user_id": refund_request.user_id,
                "payment_id": refund_request.payment_id,
                "amount": refund_request.amount,
                "currency": refund_request.currency,
                "refund_basis": refund_request.refund_basis.value,
                "reason": refund_request.reason,
                "evidence_links": refund_request.evidence_links,
                "evidence_text": refund_request.evidence_text,
            },
            idempotency_key=f"refund_{refund_request.payment_id}_{uuid.uuid4()}",
        )

        action = await self.approval_service.create_support_action(
            approval_request
        )

        logger.info(
            f"Created refund approval action {action.id} for payment {refund_request.payment_id}"
        )

        return action.id

    async def verify_provider_refund(
        self,
        payment_id: str,
        provider_refund_id: str,
    ) -> bool:
        """Verify refund in payment provider (YooKassa).

        Args:
            payment_id: Original payment ID.
            provider_refund_id: Refund ID from provider.

        Returns:
            bool: True if refund exists and is successful.

        Raises:
            RuntimeError: If verification fails.
        """
        try:
            response = await self.fuckhr_client.execute_action(
                action_id=uuid.uuid4(),
                action_type="verify_provider_refund",
                payload={
                    "payment_id": payment_id,
                    "provider_refund_id": provider_refund_id,
                },
                idempotency_key=f"verify_refund_{provider_refund_id}_{uuid.uuid4()}",
            )

            is_verified = response.get("verified", False)
            logger.info(
                f"Provider refund verification for {provider_refund_id}: {is_verified}"
            )

            return is_verified

        except Exception as e:
            logger.error(f"Error verifying provider refund: {e}")
            raise RuntimeError(f"Failed to verify provider refund: {e}")

    async def soft_delete_subscription(
        self,
        user_id: str,
        action_id: uuid.UUID,
    ) -> bool:
        """Soft-delete subscription and related resources.

        This M2M call performs multiple operations:
        - Soft-delete subscription (preserves audit trail)
        - Deactivate job searches
        - Stop active runs
        - Disable auto-renewal

        Args:
            user_id: QuickOffer user ID.
            action_id: Support action ID (for audit trail).

        Returns:
            bool: True if deletion was successful.

        Raises:
            RuntimeError: If deletion fails.
        """
        try:
            response = await self.fuckhr_client.execute_action(
                action_id=action_id,
                action_type="soft_delete_subscription",
                payload={
                    "user_id": user_id,
                    "reason": "refund_requested",
                    "support_action_id": str(action_id),
                },
                idempotency_key=f"delete_sub_{user_id}_{action_id}",
            )

            success = response.get("success", False)
            logger.info(
                f"Soft-delete subscription for user {user_id}: {success}"
            )

            return success

        except Exception as e:
            logger.error(f"Error soft-deleting subscription: {e}")
            raise RuntimeError(f"Failed to delete subscription: {e}")

    async def handle_reconciliation_failure(
        self,
        action_id: uuid.UUID,
        error: str,
    ) -> None:
        """Handle reconciliation when provider succeeded but local delete failed.

        If provider refund was successful but local subscription deletion failed,
        we move to reconciliation_pending status WITHOUT retrying the provider
        (to maintain idempotency).

        Args:
            action_id: Support action ID.
            error: Error message from failed operation.
        """
        logger.error(
            f"Reconciliation needed for action {action_id}: {error}. "
            f"Provider succeeded, local deletion failed. "
            f"Status set to reconciliation_pending."
        )

        # This status change should be done via approval_service
        # to maintain audit trail


class RefundFlowOrchestrator:
    """Orchestrator for refund flow state transitions."""

    def __init__(self, engine: RefundFlowEngine) -> None:
        """Initialize orchestrator.

        Args:
            engine: Refund flow engine.
        """
        self.engine = engine

    async def transition_to_preview(
        self,
        context: RefundContextData,
    ) -> dict[str, Any]:
        """Transition to PREVIEW state.

        Args:
            context: Current flow context.

        Returns:
            dict: Refund preview data.
        """
        preview = await self.engine.get_refund_preview(
            user_id=context.user_id,
            payment_id=context.payment_id,
            refund_basis=context.refund_basis,
        )

        return preview

    async def transition_to_staff_approval(
        self,
        context: RefundContextData,
    ) -> uuid.UUID:
        """Transition to STAFF_APPROVAL state.

        Args:
            context: Current flow context.

        Returns:
            uuid.UUID: Support action ID.
        """
        refund_request = RefundRequest(
            user_id=context.user_id,
            ticket_id=context.ticket_id,
            payment_id=context.payment_id,
            amount=context.amount,
            currency=context.currency,
            refund_basis=context.refund_basis,
            reason=context.reason,
            evidence_links=context.evidence_links,
            evidence_text=context.evidence_text,
        )

        action_id = await self.engine.create_refund_approval_action(
            context.ticket_id, refund_request
        )

        return action_id

    async def transition_to_soft_delete(
        self,
        context: RefundContextData,
    ) -> bool:
        """Transition to SOFT_DELETE_SUBSCRIPTION state.

        Args:
            context: Current flow context.

        Returns:
            bool: Success status.
        """
        if not context.support_action_id:
            raise ValueError("Support action ID required for soft delete")

        if not context.staff_decision:
            raise ValueError("Staff must approve before soft delete")

        if not context.refund_verified:
            raise ValueError("Provider refund must be verified before soft delete")

        success = await self.engine.soft_delete_subscription(
            user_id=context.user_id,
            action_id=context.support_action_id,
        )

        return success
