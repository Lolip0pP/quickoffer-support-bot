"""Mock M2M API clients for testing and demo purposes."""

import uuid
from typing import Any

from src.domain.interfaces import M2MClient


class MockFuckHRAPIClient(M2MClient):
    """Mock client for FuckHR API - returns predefined responses."""

    async def execute_action(
        self,
        action_id: uuid.UUID,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Execute action on mock FuckHR API.

        Args:
            action_id: Unique action identifier.
            action_type: Type of action to execute.
            payload: Action payload data.
            idempotency_key: Idempotency key for request deduplication.

        Returns:
            dict: Mock API response data.
        """
        # Simulate different responses based on action type
        if action_type == "escalate":
            return {
                "status": "success",
                "action_id": str(action_id),
                "escalated_to": "senior_manager",
                "timestamp": "2026-08-19T15:06:00Z",
                "message": "Issue escalated to senior management",
            }
        elif action_type == "reassign":
            return {
                "status": "success",
                "action_id": str(action_id),
                "reassigned_to": payload.get("staff_id", "staff_123"),
                "timestamp": "2026-08-19T15:06:00Z",
                "message": f"Reassigned to {payload.get('staff_id', 'staff_123')}",
            }
        elif action_type == "resolve":
            return {
                "status": "success",
                "action_id": str(action_id),
                "resolution_date": "2026-08-19T15:06:00Z",
                "message": "Issue resolved successfully",
            }
        elif action_type == "update_metadata":
            return {
                "status": "success",
                "action_id": str(action_id),
                "updated_fields": list(payload.keys()),
                "timestamp": "2026-08-19T15:06:00Z",
                "message": "Metadata updated successfully",
            }
        else:
            return {
                "status": "success",
                "action_id": str(action_id),
                "action_type": action_type,
                "timestamp": "2026-08-19T15:06:00Z",
                "message": f"Mock action {action_type} completed",
            }

    async def get_reconciliation_status(
        self, action_id: uuid.UUID
    ) -> str:
        """Get mock reconciliation status.

        Args:
            action_id: Action identifier.

        Returns:
            str: Mock reconciliation status.
        """
        # Simulate different statuses
        statuses = ["pending", "processing", "completed", "completed"]
        # Use UUID hash to get consistent status for same ID
        hash_value = hash(str(action_id)) % len(statuses)
        return statuses[hash_value]


class MockJobsAPIClient(M2MClient):
    """Mock client for Jobs API - returns predefined responses."""

    async def execute_action(
        self,
        action_id: uuid.UUID,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Execute action on mock Jobs API.

        Args:
            action_id: Unique action identifier.
            action_type: Type of action to execute.
            payload: Action payload data.
            idempotency_key: Idempotency key for request deduplication.

        Returns:
            dict: Mock API response data.
        """
        # Simulate different responses based on action type
        if action_type == "create_job":
            return {
                "status": "success",
                "action_id": str(action_id),
                "job_id": str(uuid.uuid4()),
                "title": payload.get("title", "New Position"),
                "department": payload.get("department", "Engineering"),
                "created_at": "2026-08-19T15:06:00Z",
                "message": "Job position created successfully",
            }
        elif action_type == "publish_job":
            return {
                "status": "success",
                "action_id": str(action_id),
                "job_id": payload.get("job_id"),
                "published_at": "2026-08-19T15:06:00Z",
                "message": "Job position published successfully",
            }
        elif action_type == "close_job":
            return {
                "status": "success",
                "action_id": str(action_id),
                "job_id": payload.get("job_id"),
                "closed_at": "2026-08-19T15:06:00Z",
                "message": "Job position closed successfully",
            }
        elif action_type == "referral":
            return {
                "status": "success",
                "action_id": str(action_id),
                "referral_id": str(uuid.uuid4()),
                "candidate_name": payload.get("candidate_name", "John Doe"),
                "position": payload.get("position", "Engineer"),
                "referred_at": "2026-08-19T15:06:00Z",
                "message": "Referral created successfully",
            }
        else:
            return {
                "status": "success",
                "action_id": str(action_id),
                "action_type": action_type,
                "timestamp": "2026-08-19T15:06:00Z",
                "message": f"Mock action {action_type} completed",
            }

    async def get_reconciliation_status(
        self, action_id: uuid.UUID
    ) -> str:
        """Get mock reconciliation status.

        Args:
            action_id: Action identifier.

        Returns:
            str: Mock reconciliation status.
        """
        # Simulate different statuses
        statuses = ["pending", "processing", "completed", "completed"]
        # Use UUID hash to get consistent status for same ID
        hash_value = hash(str(action_id)) % len(statuses)
        return statuses[hash_value]
