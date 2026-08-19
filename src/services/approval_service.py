"""Approval service for handling staff approvals with parameter freezing and hashing."""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.domain.entities import (
    AuditLogEntity,
    FrozenParams,
    RiskLevel,
    SupportActionEntity,
    SupportActionStatus,
    SupportActionType,
)
from src.domain.interfaces import (
    AuditLogRepository,
    SupportActionRepository,
)

logger = logging.getLogger(__name__)


class ApprovalRequest(BaseModel):
    """Request to create a support action requiring approval."""

    support_ticket_id: uuid.UUID
    action_type: SupportActionType
    risk_level: RiskLevel
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ApprovalDecision(BaseModel):
    """Decision on a support action."""

    action_id: uuid.UUID
    approved: bool
    staff_id: str
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalService:
    """Service for managing support action approvals with frozen parameters."""

    def __init__(
        self,
        action_repo: SupportActionRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        """Initialize approval service.

        Args:
            action_repo: Support action repository.
            audit_repo: Audit log repository.
        """
        self.action_repo = action_repo
        self.audit_repo = audit_repo

    def _compute_params_hash(self, params: dict[str, Any]) -> str:
        """Compute SHA256 hash of parameters.

        Args:
            params: Parameters to hash.

        Returns:
            str: SHA256 hexadecimal hash.
        """
        # Sort dict for deterministic hashing
        json_str = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    async def create_support_action(
        self,
        request: ApprovalRequest,
    ) -> SupportActionEntity:
        """Create a new support action with frozen parameters.

        Frozen parameters are immutable - any modification will invalidate approval.

        Args:
            request: Approval request with action details.

        Returns:
            SupportActionEntity: Created support action.

        Raises:
            ValueError: If parameters are invalid.
        """
        # Generate idempotency key if not provided
        idempotency_key = request.idempotency_key or str(uuid.uuid4())

        # Compute hash of parameters (frozen snapshot)
        params_hash = self._compute_params_hash(request.params)

        # Create frozen params structure
        frozen_params = FrozenParams(
            action_type=request.action_type,
            data=request.params.copy(),
        )

        # Create support action entity
        action = SupportActionEntity(
            support_ticket_id=request.support_ticket_id,
            action_type=request.action_type,
            risk_level=request.risk_level,
            frozen_params=frozen_params,
            params_hash=params_hash,
            idempotency_key=idempotency_key,
            status=SupportActionStatus.PENDING,
        )

        # Save to repository
        saved_action = await self.action_repo.create(action)

        logger.info(
            f"Created support action {saved_action.id} with hash {params_hash}"
        )

        return saved_action

    async def validate_params_integrity(
        self, action_id: uuid.UUID
    ) -> bool:
        """Validate that action parameters haven't been modified.

        Args:
            action_id: Action ID to validate.

        Returns:
            bool: True if parameters match the hash, False otherwise.
        """
        action = await self.action_repo.get_by_id(action_id)

        # Recompute hash from current frozen params
        current_hash = self._compute_params_hash(action.frozen_params.data)

        # Compare with stored hash
        params_valid = current_hash == action.params_hash

        if not params_valid:
            logger.warning(
                f"Parameter integrity check failed for action {action_id}: "
                f"expected {action.params_hash}, got {current_hash}"
            )

        return params_valid

    async def invalidate_if_params_changed(
        self, action_id: uuid.UUID
    ) -> bool:
        """Check if parameters changed and invalidate approval if needed.

        Args:
            action_id: Action ID to check.

        Returns:
            bool: True if approval was invalidated, False if params unchanged.
        """
        action = await self.action_repo.get_by_id(action_id)

        # If already executed or rejected, don't invalidate
        if action.status in (
            SupportActionStatus.EXECUTED,
            SupportActionStatus.REJECTED,
        ):
            return False

        # Check parameter integrity
        if not await self.validate_params_integrity(action_id):
            # Revert to PENDING status
            action.status = SupportActionStatus.PENDING
            action.approval_actor_id = None
            action.approved_at = None

            await self.action_repo.update(action)

            logger.warning(
                f"Invalidated approval for action {action_id} due to parameter change"
            )

            return True

        return False

    async def process_approval_decision(
        self, decision: ApprovalDecision
    ) -> SupportActionEntity:
        """Process a staff approval decision.

        Args:
            decision: Approval decision from staff.

        Returns:
            SupportActionEntity: Updated action.

        Raises:
            ValueError: If action not found or validation fails.
        """
        action = await self.action_repo.get_by_id(decision.action_id)

        # Validate parameter integrity before processing
        if not await self.validate_params_integrity(decision.action_id):
            raise ValueError(
                "Cannot process decision: action parameters have been modified"
            )

        if decision.approved:
            action.status = SupportActionStatus.APPROVED
        else:
            action.status = SupportActionStatus.REJECTED

        action.approval_actor_id = decision.staff_id
        action.approved_at = datetime.utcnow()

        # Update in repository
        updated_action = await self.action_repo.update(action)

        # Create audit log
        await self.audit_repo.create(
            AuditLogEntity(
                support_action_id=action.id,
                actor_id=decision.staff_id,
                target_id=str(action.id),
                action="approved" if decision.approved else "rejected",
                payload={
                    "reason": decision.reason,
                    "metadata": decision.metadata,
                    "params_hash": action.params_hash,
                },
            )
        )

        logger.info(
            f"Processed approval decision for action {decision.action_id}: "
            f"approved={decision.approved}, staff_id={decision.staff_id}"
        )

        return updated_action

    async def get_action_details(
        self, action_id: uuid.UUID
    ) -> dict[str, Any]:
        """Get detailed information about an action for display.

        Args:
            action_id: Action ID to retrieve.

        Returns:
            dict: Action details for display (safe for Telegram messages).
        """
        action = await self.action_repo.get_by_id(action_id)

        return {
            "id": str(action.id),
            "type": action.action_type.value,
            "risk_level": action.risk_level.value,
            "status": action.status.value,
            "params": action.frozen_params.data,
            "params_hash": action.params_hash,
            "created_at": action.created_at.isoformat() if action.created_at else None,
            "approved_by": action.approval_actor_id,
            "approval_time": (
                action.approved_at.isoformat() if action.approved_at else None
            ),
        }
