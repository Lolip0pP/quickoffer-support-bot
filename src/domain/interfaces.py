"""Domain interfaces - abstract base classes for repositories and services."""

from abc import ABC, abstractmethod
from typing import Any

import uuid

from src.domain.entities import (
    AuditLogEntity,
    ConversationEntity,
    SupportActionEntity,
    SupportTicketEntity,
)


class ConversationRepository(ABC):
    """Abstract repository for Conversation operations."""

    @abstractmethod
    async def create(self, entity: ConversationEntity) -> ConversationEntity:
        """Create a new conversation."""

    @abstractmethod
    async def get_by_id(self, conversation_id: uuid.UUID) -> ConversationEntity:
        """Get conversation by ID."""

    @abstractmethod
    async def get_by_tg_id(self, tg_id: int) -> ConversationEntity | None:
        """Get conversation by Telegram ID."""

    @abstractmethod
    async def update(self, entity: ConversationEntity) -> ConversationEntity:
        """Update conversation."""

    @abstractmethod
    async def delete(self, conversation_id: uuid.UUID) -> None:
        """Delete conversation."""


class SupportTicketRepository(ABC):
    """Abstract repository for SupportTicket operations."""

    @abstractmethod
    async def create(self, entity: SupportTicketEntity) -> SupportTicketEntity:
        """Create a new support ticket."""

    @abstractmethod
    async def get_by_id(self, ticket_id: uuid.UUID) -> SupportTicketEntity:
        """Get support ticket by ID."""

    @abstractmethod
    async def get_by_conversation_id(
        self, conversation_id: uuid.UUID
    ) -> list[SupportTicketEntity]:
        """Get all tickets for a conversation."""

    @abstractmethod
    async def update(self, entity: SupportTicketEntity) -> SupportTicketEntity:
        """Update support ticket."""

    @abstractmethod
    async def delete(self, ticket_id: uuid.UUID) -> None:
        """Delete support ticket."""


class SupportActionRepository(ABC):
    """Abstract repository for SupportAction operations."""

    @abstractmethod
    async def create(self, entity: SupportActionEntity) -> SupportActionEntity:
        """Create a new support action."""

    @abstractmethod
    async def get_by_id(self, action_id: uuid.UUID) -> SupportActionEntity:
        """Get support action by ID."""

    @abstractmethod
    async def get_by_idempotency_key(
        self, key: str
    ) -> SupportActionEntity | None:
        """Get support action by idempotency key."""

    @abstractmethod
    async def update(self, entity: SupportActionEntity) -> SupportActionEntity:
        """Update support action."""

    @abstractmethod
    async def delete(self, action_id: uuid.UUID) -> None:
        """Delete support action."""


class AuditLogRepository(ABC):
    """Abstract repository for AuditLog operations."""

    @abstractmethod
    async def create(self, entity: AuditLogEntity) -> AuditLogEntity:
        """Create an audit log entry."""

    @abstractmethod
    async def get_by_action_id(
        self, action_id: uuid.UUID
    ) -> list[AuditLogEntity]:
        """Get audit logs for a support action."""

    @abstractmethod
    async def get_by_actor_id(self, actor_id: str) -> list[AuditLogEntity]:
        """Get audit logs for an actor."""


class LLMService(ABC):
    """Abstract LLM service - READ-ONLY operations only."""

    @abstractmethod
    async def generate_response(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> str:
        """Generate LLM response (read-only)."""

    @abstractmethod
    async def analyze_ticket(
        self, ticket_content: str
    ) -> dict[str, Any]:
        """Analyze support ticket content (read-only)."""

    @abstractmethod
    async def suggest_resolution(
        self, ticket_id: uuid.UUID
    ) -> str:
        """Suggest resolution for a ticket (read-only)."""


class M2MClient(ABC):
    """Abstract M2M (Machine-to-Machine) API client."""

    @abstractmethod
    async def execute_action(
        self,
        action_id: uuid.UUID,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Execute action on external API with idempotency."""

    @abstractmethod
    async def get_reconciliation_status(
        self, action_id: uuid.UUID
    ) -> str:
        """Get reconciliation status from external API."""
