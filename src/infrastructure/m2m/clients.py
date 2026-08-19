"""M2M API clients for internal services."""

import uuid
from typing import Any

import httpx

from src.core.config import settings
from src.domain.interfaces import M2MClient


class FuckHRAPIClient(M2MClient):
    """Client for FuckHR API - HR and personnel management."""

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize FuckHR API client.

        Args:
            base_url: Base URL for FuckHR API.
        """
        self.base_url = base_url or settings.fuckhr_api_base_url
        self.api_key = settings.m2m_api_key

    async def execute_action(
        self,
        action_id: uuid.UUID,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Execute action on FuckHR API with idempotency.

        Args:
            action_id: Unique action identifier.
            action_type: Type of action to execute.
            payload: Action payload data.
            idempotency_key: Idempotency key for request deduplication.

        Returns:
            dict: API response data.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
            "Trace-ID": str(action_id),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/actions/{action_type}",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_reconciliation_status(
        self, action_id: uuid.UUID
    ) -> str:
        """Get reconciliation status from FuckHR API.

        Args:
            action_id: Action identifier.

        Returns:
            str: Reconciliation status.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Trace-ID": str(action_id),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/actions/{action_id}/status",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("status", "pending")


class JobsAPIClient(M2MClient):
    """Client for Jobs API - job and position management."""

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize Jobs API client.

        Args:
            base_url: Base URL for Jobs API.
        """
        self.base_url = base_url or settings.jobs_api_base_url
        self.api_key = settings.m2m_api_key

    async def execute_action(
        self,
        action_id: uuid.UUID,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Execute action on Jobs API with idempotency.

        Args:
            action_id: Unique action identifier.
            action_type: Type of action to execute.
            payload: Action payload data.
            idempotency_key: Idempotency key for request deduplication.

        Returns:
            dict: API response data.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
            "Trace-ID": str(action_id),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/actions/{action_type}",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_reconciliation_status(
        self, action_id: uuid.UUID
    ) -> str:
        """Get reconciliation status from Jobs API.

        Args:
            action_id: Action identifier.

        Returns:
            str: Reconciliation status.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Trace-ID": str(action_id),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/actions/{action_id}/status",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("status", "pending")
