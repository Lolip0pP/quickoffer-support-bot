"""Staff approval workflow engine with role-based access control."""

import json
import logging
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.domain.entities import SupportActionEntity

logger = logging.getLogger(__name__)


class StaffRole(str, Enum):
    """Staff role enumeration."""

    SUPPORT = "support"
    FINANCE = "finance"
    ADMIN = "admin"


class StaffMember(BaseModel):
    """Staff member profile."""

    staff_id: str
    name: str
    roles: list[StaffRole] = Field(default_factory=list)
    is_active: bool = True


class ApprovalCard(BaseModel):
    """Formatted approval card for Telegram."""

    action_id: str
    ticket_id: str
    action_type: str
    risk_level: str
    params: dict[str, Any] = Field(default_factory=dict)
    params_hash: str
    created_at: str | None = None
    formatted_message: str = ""

    def generate_message(self) -> str:
        """Generate formatted message for Telegram.

        Returns:
            str: Telegram-formatted message with action details.
        """
        params_str = json.dumps(self.params, indent=2, ensure_ascii=False)

        message = (
            f"📋 *APPROVAL REQUIRED*\n\n"
            f"*Action ID:* `{self.action_id}`\n"
            f"*Ticket ID:* `{self.ticket_id}`\n"
            f"*Type:* {self.action_type}\n"
            f"*Risk Level:* 🔴 {self.risk_level.upper()}\n"
            f"*Created:* {self.created_at}\n\n"
            f"*Parameters (frozen):*\n"
            f"```json\n{params_str}\n```\n"
            f"*Hash:* `{self.params_hash}`\n\n"
            f"⚠️ Any parameter change invalidates this approval."
        )

        return message


class StaffApprovalEngine:
    """Engine for managing staff approvals with role-based access."""

    def __init__(self, staff_allowlist: dict[str, list[str]] | None = None) -> None:
        """Initialize staff approval engine.

        Args:
            staff_allowlist: Dict mapping staff_id -> list of roles.
                           If None, all staff are allowed (for development).
        """
        self.staff_allowlist = staff_allowlist or {}

    def add_staff_member(
        self, staff_id: str, roles: list[StaffRole]
    ) -> None:
        """Add staff member to allowlist.

        Args:
            staff_id: Unique staff identifier.
            roles: List of roles for this staff member.
        """
        self.staff_allowlist[staff_id] = [role.value for role in roles]
        logger.info(f"Added staff member {staff_id} with roles: {roles}")

    def remove_staff_member(self, staff_id: str) -> None:
        """Remove staff member from allowlist.

        Args:
            staff_id: Staff identifier to remove.
        """
        if staff_id in self.staff_allowlist:
            del self.staff_allowlist[staff_id]
            logger.info(f"Removed staff member {staff_id}")

    def can_approve(
        self,
        staff_id: str,
        required_role: StaffRole | None = None,
    ) -> bool:
        """Check if staff member can approve actions.

        Args:
            staff_id: Staff identifier to check.
            required_role: Specific role required (if any).

        Returns:
            bool: True if staff member is authorized.
        """
        # If no allowlist configured, allow all (dev mode)
        if not self.staff_allowlist:
            logger.warning(
                f"No staff allowlist configured - allowing all staff (DEV MODE)"
            )
            return True

        if staff_id not in self.staff_allowlist:
            logger.warning(f"Staff {staff_id} not in allowlist")
            return False

        if required_role:
            allowed_roles = self.staff_allowlist[staff_id]
            if required_role.value not in allowed_roles:
                logger.warning(
                    f"Staff {staff_id} does not have required role: {required_role}"
                )
                return False

        return True

    def get_staff_roles(self, staff_id: str) -> list[str]:
        """Get roles for a staff member.

        Args:
            staff_id: Staff identifier.

        Returns:
            list: List of role values.
        """
        return self.staff_allowlist.get(staff_id, [])

    def create_approval_card(
        self, action: SupportActionEntity, ticket_id: str
    ) -> ApprovalCard:
        """Create approval card from action entity.

        Args:
            action: Support action entity.
            ticket_id: Ticket ID for reference.

        Returns:
            ApprovalCard: Formatted approval card.
        """
        card = ApprovalCard(
            action_id=str(action.id),
            ticket_id=ticket_id,
            action_type=action.action_type.value,
            risk_level=action.risk_level.value,
            params=action.frozen_params.data,
            params_hash=action.params_hash,
            created_at=(
                action.created_at.isoformat() if action.created_at else None
            ),
        )

        card.formatted_message = card.generate_message()
        return card

    def format_action_preview(
        self, action: SupportActionEntity
    ) -> str:
        """Format action details for preview (short format).

        Args:
            action: Support action entity.

        Returns:
            str: Formatted preview string.
        """
        params_summary = ", ".join(
            f"{k}={v}" for k, v in action.frozen_params.data.items()
        )[:100]

        preview = (
            f"Action: {action.action_type.value}\n"
            f"Risk: {action.risk_level.value}\n"
            f"Params: {params_summary}\n"
            f"Status: {action.status.value}"
        )

        return preview

    def format_decision_confirmation(
        self,
        action_id: uuid.UUID,
        approved: bool,
        staff_id: str,
        reason: str | None = None,
    ) -> str:
        """Format decision confirmation message.

        Args:
            action_id: Action ID.
            approved: Whether approved or rejected.
            staff_id: Staff member who made decision.
            reason: Optional reason for decision.

        Returns:
            str: Formatted confirmation message.
        """
        status = "✅ APPROVED" if approved else "❌ REJECTED"
        message = (
            f"{status}\n\n"
            f"*Action ID:* `{action_id}`\n"
            f"*Staff:* {staff_id}\n"
        )

        if reason:
            message += f"*Reason:* {reason}\n"

        return message
