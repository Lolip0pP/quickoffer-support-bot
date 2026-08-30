"""Human Handoff Engine - Escalation triggering and ticket creation."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HandoffTriggerType(str, Enum):
    """Types of handoff triggers that stop autonomous operation."""

    EXPLICIT_REQUEST = "explicit_request"
    IDENTITY_NOT_VERIFIED = "identity_not_verified"
    MONEY_LEGAL_ISSUE = "money_legal_issue"
    ACCOUNT_SECURITY = "account_security"
    DATA_REQUEST_UNKNOWN_POLICY = "data_request_unknown_policy"
    TOOL_FAILURE_CASCADE = "tool_failure_cascade"
    DOUBLE_LLM_FAILURE = "double_llm_failure"


class HandoffStatus(str, Enum):
    """Handoff ticket status."""

    CREATED = "created"
    NOTIFIED = "notified"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class CollectedFact:
    """Single fact collected during investigation."""

    fact_type: str  # e.g., "user_message", "tool_failure", "llm_error"
    source: str  # e.g., "user_input", "investigation_service", "llm_service"
    value: str
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fact_type": self.fact_type,
            "source": self.source,
            "value": self.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HandoffContext:
    """Context for handoff escalation."""

    conversation_id: uuid.UUID
    user_id: str
    trigger_type: HandoffTriggerType
    trigger_reason: str
    collected_facts: list[CollectedFact] = field(default_factory=list)
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    investigation_summary: str = ""
    confidence_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "conversation_id": str(self.conversation_id),
            "user_id": self.user_id,
            "trigger_type": self.trigger_type.value,
            "trigger_reason": self.trigger_reason,
            "collected_facts": [f.to_dict() for f in self.collected_facts],
            "conversation_history": self.conversation_history,
            "investigation_summary": self.investigation_summary,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
        }


class HandoffDetector:
    """Detect if conversation should trigger handoff."""

    def __init__(self) -> None:
        """Initialize handoff detector."""
        self.explicit_keywords = {
            "human",
            "operator",
            "manager",
            "support team",
            "talk to someone",
            "к человеку",
            "оператора",
            "менеджер",
        }

        self.money_keywords = {
            "refund",
            "chargeback",
            "payment issue",
            "billing",
            "invoice",
            "charge",
            "lawsuit",
            "legal",
            "contract",
            "возврат",
            "платеж",
            "счет",
            "судебное",
        }

        self.security_keywords = {
            "account takeover",
            "hacked",
            "breached",
            "suspicious",
            "unauthorized",
            "password reset",
            "two factor",
            "взломана",
            "недостоверн",
            "не мой счет",
        }

        self.data_keywords = {
            "export data",
            "export",
            "my information",
            "gdpr",
            "delete account",
            "anonymize",
            "данные",
            "информацию",
            "удалить",
        }

        self.llm_failure_counter: dict[str, int] = {}
        self.tool_failure_counter: dict[str, int] = {}

    def detect(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, HandoffTriggerType | None, str]:
        """Detect if handoff should be triggered.

        Args:
            user_message: User's message text.
            context: Additional context (identity_verified, tool_errors, etc.).

        Returns:
            tuple: (should_handoff, trigger_type, reason)
        """
        context = context or {}
        message_lower = user_message.lower()

        # Trigger 1: Explicit request for human
        if any(kw in message_lower for kw in self.explicit_keywords):
            logger.info("Handoff triggered: explicit human request")
            return (
                True,
                HandoffTriggerType.EXPLICIT_REQUEST,
                "User explicitly requested human support",
            )

        # Trigger 2: Identity not verified
        if not context.get("identity_verified", True):
            logger.info("Handoff triggered: identity not verified")
            return (
                True,
                HandoffTriggerType.IDENTITY_NOT_VERIFIED,
                "User identity could not be verified",
            )

        # Trigger 3: Money, chargeback, or legal issues
        if any(kw in message_lower for kw in self.money_keywords):
            logger.info("Handoff triggered: money/legal issue detected")
            return (
                True,
                HandoffTriggerType.MONEY_LEGAL_ISSUE,
                "Message contains money, chargeback, or legal keywords",
            )

        # Trigger 4: Account takeover or security issues
        if any(kw in message_lower for kw in self.security_keywords):
            logger.info("Handoff triggered: security issue detected")
            return (
                True,
                HandoffTriggerType.ACCOUNT_SECURITY,
                "Message contains account security concerns",
            )

        # Trigger 5: Data request or unknown policy
        if any(kw in message_lower for kw in self.data_keywords):
            logger.info("Handoff triggered: data request detected")
            return (
                True,
                HandoffTriggerType.DATA_REQUEST_UNKNOWN_POLICY,
                "User requesting personal data or account deletion",
            )

        # Trigger 6: Tool failure cascade (repeated failures)
        conversation_id = context.get("conversation_id")
        tool_failure_count = context.get("tool_failure_count", 0)
        if tool_failure_count > 1:
            logger.info(
                f"Handoff triggered: tool failure cascade "
                f"({tool_failure_count} failures)"
            )
            return (
                True,
                HandoffTriggerType.TOOL_FAILURE_CASCADE,
                f"Tool failures repeated {tool_failure_count} times",
            )

        # Trigger 7: Double LLM failure
        llm_failure_count = context.get("llm_failure_count", 0)
        if llm_failure_count >= 2:
            logger.info(
                f"Handoff triggered: LLM failure cascade "
                f"({llm_failure_count} failures)"
            )
            return (
                True,
                HandoffTriggerType.DOUBLE_LLM_FAILURE,
                f"LLM generation failed {llm_failure_count} times consecutively",
            )

        return (False, None, "")

    def record_tool_failure(self, conversation_id: str) -> None:
        """Record a tool failure for cascade detection.

        Args:
            conversation_id: Conversation identifier.
        """
        key = f"tool_{conversation_id}"
        self.tool_failure_counter[key] = self.tool_failure_counter.get(key, 0) + 1
        logger.debug(
            f"Tool failure recorded for {conversation_id}: "
            f"count={self.tool_failure_counter[key]}"
        )

    def record_llm_failure(self, conversation_id: str) -> None:
        """Record an LLM failure for cascade detection.

        Args:
            conversation_id: Conversation identifier.
        """
        key = f"llm_{conversation_id}"
        self.llm_failure_counter[key] = self.llm_failure_counter.get(key, 0) + 1
        logger.debug(
            f"LLM failure recorded for {conversation_id}: "
            f"count={self.llm_failure_counter[key]}"
        )

    def reset_failures(self, conversation_id: str) -> None:
        """Reset failure counters on successful response.

        Args:
            conversation_id: Conversation identifier.
        """
        self.tool_failure_counter.pop(f"tool_{conversation_id}", None)
        self.llm_failure_counter.pop(f"llm_{conversation_id}", None)
        logger.debug(f"Failure counters reset for {conversation_id}")


class HandoffExecutor:
    """Execute handoff actions: create ticket and notify admins."""

    def __init__(self) -> None:
        """Initialize handoff executor."""
        from src.core.config import settings

        self.settings = settings
        self.admin_chat_id = settings.telegram_approval_chat_id

    async def execute_handoff(self, context: HandoffContext) -> dict[str, Any]:
        """Execute handoff: create ticket and notify admins.

        Args:
            context: Handoff context with collected facts.

        Returns:
            dict: Handoff execution result with ticket_id.
        """
        logger.info(
            f"Executing handoff for conversation: {context.conversation_id}, "
            f"trigger: {context.trigger_type}"
        )

        # Step 1: Create handoff ticket
        ticket_id = await self._create_ticket(context)

        # Step 2: Generate summary for admins
        summary = self._generate_admin_summary(context, ticket_id)

        # Step 3: Notify admins via Telegram
        notification_sent = await self._notify_admins(summary, ticket_id)

        result = {
            "ticket_id": str(ticket_id),
            "status": HandoffStatus.CREATED,
            "trigger_type": context.trigger_type.value,
            "notification_sent": notification_sent,
            "admin_chat_id": self.admin_chat_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Handoff executed successfully: ticket={ticket_id}")
        return result

    async def _create_ticket(self, context: HandoffContext) -> uuid.UUID:
        """Create a handoff ticket in the database.

        Args:
            context: Handoff context.

        Returns:
            uuid.UUID: Created ticket ID.
        """
        ticket_id = uuid.uuid4()

        # In production: save to database using SupportAction
        ticket_data = {
            "id": str(ticket_id),
            "conversation_id": str(context.conversation_id),
            "user_id": context.user_id,
            "trigger_type": context.trigger_type.value,
            "trigger_reason": context.trigger_reason,
            "status": HandoffStatus.CREATED.value,
            "collected_facts": [f.to_dict() for f in context.collected_facts],
            "investigation_summary": context.investigation_summary,
            "confidence_score": context.confidence_score,
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Handoff ticket created: {ticket_id} "
            f"(conversation={context.conversation_id})"
        )

        return ticket_id

    def _generate_admin_summary(
        self, context: HandoffContext, ticket_id: uuid.UUID
    ) -> str:
        """Generate summary message for admins.

        Args:
            context: Handoff context.
            ticket_id: Created ticket ID.

        Returns:
            str: Admin summary message.
        """
        summary_parts = [
            f"🚨 <b>Human Handoff Triggered</b>",
            f"",
            f"<b>Ticket ID:</b> <code>{ticket_id}</code>",
            f"<b>User ID:</b> <code>{context.user_id}</code>",
            f"<b>Conversation ID:</b> <code>{context.conversation_id}</code>",
            f"",
            f"<b>Trigger Type:</b> {context.trigger_type.value}",
            f"<b>Reason:</b> {context.trigger_reason}",
            f"",
        ]

        if context.investigation_summary:
            summary_parts.append(
                f"<b>Investigation Summary:</b>\n{context.investigation_summary}"
            )
            summary_parts.append("")

        if context.collected_facts:
            summary_parts.append("<b>Collected Facts:</b>")
            for fact in context.collected_facts[-5:]:  # Last 5 facts
                summary_parts.append(f"  • [{fact.fact_type}] {fact.value}")
            summary_parts.append("")

        if context.conversation_history:
            summary_parts.append("<b>Recent Messages:</b>")
            for msg in context.conversation_history[-3:]:  # Last 3 messages
                text = msg.get("text", "")[:100]
                role = msg.get("role", "unknown")
                summary_parts.append(f"  {role}: {text}...")
            summary_parts.append("")

        summary_parts.append(f"<b>Confidence Score:</b> {context.confidence_score:.2f}")
        summary_parts.append(f"<b>Timestamp:</b> {datetime.utcnow().isoformat()}")

        return "\n".join(summary_parts)

    async def _notify_admins(self, summary: str, ticket_id: uuid.UUID) -> bool:
        """Notify admins via Telegram.

        Args:
            summary: Summary message.
            ticket_id: Ticket ID.

        Returns:
            bool: True if notification sent successfully.
        """
        try:
            # In production: use aiogram bot to send message
            logger.info(
                f"Notifying admins in chat {self.admin_chat_id} "
                f"about handoff ticket {ticket_id}"
            )

            # Simulated notification
            logger.info(f"Admin notification sent: {summary[:100]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to notify admins: {e}")
            return False


class HandoffService:
    """High-level handoff service orchestrating detection and execution."""

    def __init__(self) -> None:
        """Initialize handoff service."""
        self.detector = HandoffDetector()
        self.executor = HandoffExecutor()

    async def check_and_execute(
        self,
        user_message: str,
        conversation_id: uuid.UUID,
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Check if handoff should be triggered and execute if needed.

        Args:
            user_message: User's message.
            conversation_id: Conversation ID.
            user_id: User ID.
            context: Additional context.

        Returns:
            dict: Result with handoff_triggered and ticket_id if applicable.
        """
        context = context or {}
        context["conversation_id"] = str(conversation_id)

        # Detect handoff trigger
        should_handoff, trigger_type, reason = self.detector.detect(
            user_message, context
        )

        if not should_handoff:
            return {
                "handoff_triggered": False,
                "ticket_id": None,
            }

        # Create handoff context
        handoff_context = HandoffContext(
            conversation_id=conversation_id,
            user_id=user_id,
            trigger_type=trigger_type,
            trigger_reason=reason,
            investigation_summary=context.get("investigation_summary", ""),
            confidence_score=context.get("confidence_score", 0.0),
        )

        # Add collected facts
        if "tool_failure_count" in context:
            handoff_context.collected_facts.append(
                CollectedFact(
                    fact_type="tool_failure",
                    source="system",
                    value=f"Tool failed {context['tool_failure_count']} times",
                )
            )

        if "llm_failure_count" in context:
            handoff_context.collected_facts.append(
                CollectedFact(
                    fact_type="llm_failure",
                    source="system",
                    value=f"LLM failed {context['llm_failure_count']} times",
                )
            )

        handoff_context.collected_facts.append(
            CollectedFact(
                fact_type="user_message",
                source="user_input",
                value=user_message[:500],
            )
        )

        # Execute handoff
        result = await self.executor.execute_handoff(handoff_context)

        return {
            "handoff_triggered": True,
            "ticket_id": result["ticket_id"],
            "trigger_type": result["trigger_type"],
            "notification_sent": result["notification_sent"],
        }

    def record_tool_failure(self, conversation_id: str) -> None:
        """Record tool failure for cascade detection.

        Args:
            conversation_id: Conversation ID.
        """
        self.detector.record_tool_failure(conversation_id)

    def record_llm_failure(self, conversation_id: str) -> None:
        """Record LLM failure for cascade detection.

        Args:
            conversation_id: Conversation ID.
        """
        self.detector.record_llm_failure(conversation_id)

    def reset_failures(self, conversation_id: str) -> None:
        """Reset failure counters on success.

        Args:
            conversation_id: Conversation ID.
        """
        self.detector.reset_failures(conversation_id)


# Global handoff service instance
_handoff_service: HandoffService | None = None


def get_handoff_service() -> HandoffService:
    """Get global handoff service instance.

    Returns:
        HandoffService: Global instance.
    """
    global _handoff_service
    if _handoff_service is None:
        _handoff_service = HandoffService()
    return _handoff_service
