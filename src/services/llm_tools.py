"""Read-Only Tools Registry for LLM - Strictly Isolated from Mutations."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class LLMToolError(Exception):
    """Base exception for LLM tool errors."""

    pass


@dataclass
class ToolResult:
    """Result from tool execution."""

    success: bool
    data: dict[str, Any] | None
    error: str | None = None
    timestamp: datetime = None

    def __post_init__(self) -> None:
        """Set default timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class ReadOnlyTool(ABC):
    """Abstract base class for read-only LLM tools.

    No mutations, no side effects, no state changes.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for LLM."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute tool (read-only operation).

        Args:
            **kwargs: Tool-specific arguments.

        Returns:
            ToolResult: Execution result.
        """
        pass


class ApprovedFAQTool(ReadOnlyTool):
    """Tool for retrieving approved FAQ entries from curated KB."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "approved_faq"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve frequently asked questions and answers "
            "from the approved knowledge base. "
            "Use this for common support questions. "
            "Only returns published FAQ entries."
        )

    async def execute(self, query: str | None = None) -> ToolResult:
        """Execute FAQ retrieval.

        Args:
            query: Search query for FAQ (optional).

        Returns:
            ToolResult: FAQ entries.
        """
        try:
            # In production: fetch from approved KB service
            faq_data = {
                "entries": [
                    {
                        "question": "How do I reset my password?",
                        "answer": "Visit account settings and click reset.",
                    },
                    {
                        "question": "What payment methods are accepted?",
                        "answer": (
                            "We accept credit cards and digital wallets."
                        ),
                    },
                ],
                "total_count": 2,
            }

            logger.info(f"FAQ retrieval executed for query: {query}")
            return ToolResult(success=True, data=faq_data)
        except Exception as e:
            logger.error(f"FAQ retrieval failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class UserSupportSnapshotTool(ReadOnlyTool):
    """Tool for retrieving user support interaction history snapshot."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "user_support_snapshot"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve a snapshot of the current user's support "
            "interaction history (tickets, issues, status). "
            "Read-only view only. "
            "Requires user authentication."
        )

    async def execute(
        self, user_id: str | None = None
    ) -> ToolResult:
        """Execute snapshot retrieval.

        Args:
            user_id: User identifier.

        Returns:
            ToolResult: Support history snapshot.
        """
        if not user_id:
            return ToolResult(
                success=False,
                data=None,
                error="user_id is required",
            )

        try:
            # In production: fetch from support ticket repository
            snapshot_data = {
                "user_id": user_id,
                "total_tickets": 3,
                "recent_tickets": [
                    {
                        "ticket_id": "TKT-001",
                        "status": "resolved",
                        "created_at": "2024-08-15",
                    },
                ],
                "open_issues": 0,
            }

            logger.info(
                f"Support snapshot retrieved for user: {user_id}"
            )
            return ToolResult(success=True, data=snapshot_data)
        except Exception as e:
            logger.error(f"Support snapshot retrieval failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class SubscriptionStatusTool(ReadOnlyTool):
    """Tool for checking user subscription status."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "subscription_status"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Check the current subscription status of a user. "
            "Returns plan type, expiration date, and features. "
            "Requires user authentication."
        )

    async def execute(
        self, user_id: str | None = None
    ) -> ToolResult:
        """Execute subscription status check.

        Args:
            user_id: User identifier.

        Returns:
            ToolResult: Subscription information.
        """
        if not user_id:
            return ToolResult(
                success=False,
                data=None,
                error="user_id is required",
            )

        try:
            # In production: fetch from subscription service
            status_data = {
                "user_id": user_id,
                "plan": "premium",
                "status": "active",
                "expiry_date": "2025-12-31",
                "renewal_date": "2025-09-01",
                "features": ["advanced_support", "priority_queue"],
            }

            logger.info(
                f"Subscription status checked for user: {user_id}"
            )
            return ToolResult(success=True, data=status_data)
        except Exception as e:
            logger.error(f"Subscription status check failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class MaskedPaymentsTool(ReadOnlyTool):
    """Tool for retrieving masked recent payment history."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "masked_payments"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve masked payment history (last 4 digits only). "
            "Shows transaction history without sensitive data. "
            "Requires user authentication."
        )

    async def execute(
        self, user_id: str | None = None, limit: int = 5
    ) -> ToolResult:
        """Execute masked payments retrieval.

        Args:
            user_id: User identifier.
            limit: Number of recent payments to return.

        Returns:
            ToolResult: Masked payment history.
        """
        if not user_id:
            return ToolResult(
                success=False,
                data=None,
                error="user_id is required",
            )

        try:
            # In production: fetch from billing service
            payments_data = {
                "user_id": user_id,
                "total_transactions": 10,
                "recent_payments": [
                    {
                        "date": "2024-08-18",
                        "amount": 99.99,
                        "card_last_4": "4242",
                        "status": "completed",
                    },
                    {
                        "date": "2024-07-18",
                        "amount": 99.99,
                        "card_last_4": "4242",
                        "status": "completed",
                    },
                ],
            }

            logger.info(
                f"Masked payments retrieved for user: {user_id}"
            )
            return ToolResult(success=True, data=payments_data)
        except Exception as e:
            logger.error(f"Masked payments retrieval failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class SearchHealthTool(ReadOnlyTool):
    """Tool for checking search service health and recent errors."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "search_health"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Check the health status of search services. "
            "Returns recent errors, indexing status, and performance metrics."
        )

    async def execute(self) -> ToolResult:
        """Execute search health check.

        Returns:
            ToolResult: Search health information.
        """
        try:
            # In production: query monitoring/health endpoints
            health_data = {
                "status": "healthy",
                "uptime_percent": 99.95,
                "recent_errors": [],
                "indexing_status": "current",
                "last_check": datetime.utcnow().isoformat(),
            }

            logger.info("Search health check executed")
            return ToolResult(success=True, data=health_data)
        except Exception as e:
            logger.error(f"Search health check failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class CurrentIncidentsTool(ReadOnlyTool):
    """Tool for retrieving currently active public incidents."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "current_incidents"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve currently active service incidents "
            "that are publicly disclosed. "
            "Useful for explaining service issues."
        )

    async def execute(self) -> ToolResult:
        """Execute incident retrieval.

        Returns:
            ToolResult: Current incidents.
        """
        try:
            # In production: fetch from status page service
            incidents_data = {
                "active_incidents": [],
                "recent_resolved": [
                    {
                        "title": "Database maintenance",
                        "resolved_at": "2024-08-17",
                        "duration_minutes": 30,
                    },
                ],
                "total_active": 0,
            }

            logger.info("Current incidents retrieved")
            return ToolResult(success=True, data=incidents_data)
        except Exception as e:
            logger.error(f"Incident retrieval failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class PromoEligibilityTool(ReadOnlyTool):
    """Tool for checking user eligibility for promotional codes."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "promo_eligibility"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Check if a user is eligible for promotional offers. "
            "Returns available promos and eligibility status. "
            "Requires user authentication."
        )

    async def execute(
        self, user_id: str | None = None
    ) -> ToolResult:
        """Execute promo eligibility check.

        Args:
            user_id: User identifier.

        Returns:
            ToolResult: Eligibility information.
        """
        if not user_id:
            return ToolResult(
                success=False,
                data=None,
                error="user_id is required",
            )

        try:
            # In production: fetch from promo service
            eligibility_data = {
                "user_id": user_id,
                "eligible": True,
                "available_promos": [
                    {
                        "code": "WELCOME10",
                        "discount": "10%",
                        "expires": "2024-12-31",
                    },
                ],
                "used_promos": ["SUMMER20"],
            }

            logger.info(
                f"Promo eligibility checked for user: {user_id}"
            )
            return ToolResult(success=True, data=eligibility_data)
        except Exception as e:
            logger.error(f"Promo eligibility check failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class JobsPublicStatusTool(ReadOnlyTool):
    """Tool for retrieving public job vacancy status."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "jobs_public_status"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Retrieve publicly listed job vacancy information. "
            "Shows open positions, departments, and locations."
        )

    async def execute(self) -> ToolResult:
        """Execute jobs status retrieval.

        Returns:
            ToolResult: Public job information.
        """
        try:
            # In production: fetch from jobs service
            jobs_data = {
                "open_positions": 5,
                "departments": ["engineering", "sales", "support"],
                "featured_roles": [
                    {
                        "title": "Senior Backend Engineer",
                        "department": "engineering",
                        "location": "remote",
                    },
                ],
            }

            logger.info("Public jobs status retrieved")
            return ToolResult(success=True, data=jobs_data)
        except Exception as e:
            logger.error(f"Jobs status retrieval failed: {e}")
            return ToolResult(success=False, data=None, error=str(e))


class ReadOnlyToolsRegistry:
    """Registry and manager for read-only LLM tools.

    Strictly enforces that only approved read-only tools are available.
    No mutation tools, no shell access, no raw SQL.
    """

    def __init__(self) -> None:
        """Initialize tools registry."""
        self.tools: dict[str, ReadOnlyTool] = {
            "approved_faq": ApprovedFAQTool(),
            "user_support_snapshot": UserSupportSnapshotTool(),
            "subscription_status": SubscriptionStatusTool(),
            "masked_payments": MaskedPaymentsTool(),
            "search_health": SearchHealthTool(),
            "current_incidents": CurrentIncidentsTool(),
            "promo_eligibility": PromoEligibilityTool(),
            "jobs_public_status": JobsPublicStatusTool(),
        }
        logger.info(
            f"Initialized ReadOnlyToolsRegistry with "
            f"{len(self.tools)} tools"
        )

    def get_tool(self, name: str) -> ReadOnlyTool | None:
        """Get a tool by name.

        Args:
            name: Tool name.

        Returns:
            ReadOnlyTool or None if not found.
        """
        return self.tools.get(name)

    def get_available_tools(self) -> list[dict[str, str]]:
        """Get list of available tools for LLM context.

        Returns:
            list of dict with name and description.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in self.tools.values()
        ]

    async def execute_tool(
        self, tool_name: str, **kwargs: Any
    ) -> ToolResult:
        """Execute a tool with arguments.

        Args:
            tool_name: Name of the tool to execute.
            **kwargs: Tool-specific arguments.

        Returns:
            ToolResult: Execution result.

        Raises:
            LLMToolError: If tool not found or execution fails.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"Requested tool not found: {tool_name}")
            raise LLMToolError(f"Tool not found: {tool_name}")

        logger.info(
            f"Executing tool: {tool_name} with args: {list(kwargs.keys())}"
        )

        try:
            result = await tool.execute(**kwargs)
            logger.info(
                f"Tool {tool_name} executed with success={result.success}"
            )
            return result
        except Exception as e:
            logger.error(
                f"Tool {tool_name} execution failed: {e}"
            )
            raise LLMToolError(
                f"Tool execution failed: {tool_name} - {str(e)}"
            )


# Global registry instance
_tools_registry: ReadOnlyToolsRegistry | None = None


def get_tools_registry() -> ReadOnlyToolsRegistry:
    """Get global tools registry instance.

    Returns:
        ReadOnlyToolsRegistry: Global instance.
    """
    global _tools_registry
    if _tools_registry is None:
        _tools_registry = ReadOnlyToolsRegistry()
    return _tools_registry
