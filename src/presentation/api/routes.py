"""FastAPI routes for internal webhooks and health checks."""

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1", tags=["internal"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        dict: Health status.
    """
    return {"status": "healthy", "service": "support-bot"}


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint.

    Returns:
        dict: Readiness status.
    """
    return {"ready": True, "service": "support-bot"}


@router.post("/webhooks/approval")
async def approval_webhook(payload: dict[str, Any]) -> dict[str, str]:
    """Webhook for approval notifications from management API.

    Args:
        payload: Approval payload with action_id and status.

    Returns:
        dict: Acknowledgment.

    Raises:
        HTTPException: If payload validation fails.
    """
    action_id = payload.get("action_id")
    approval_status = payload.get("status")

    if not action_id or not approval_status:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: action_id, status",
        )

    return {
        "acknowledged": True,
        "action_id": action_id,
        "status": approval_status,
    }


@router.post("/webhooks/reconciliation")
async def reconciliation_webhook(
    payload: dict[str, Any],
) -> dict[str, str]:
    """Webhook for reconciliation status updates from external APIs.

    Args:
        payload: Reconciliation payload with action_id and reconciliation_status.

    Returns:
        dict: Acknowledgment.

    Raises:
        HTTPException: If payload validation fails.
    """
    action_id = payload.get("action_id")
    reconciliation_status = payload.get("reconciliation_status")

    if not action_id or not reconciliation_status:
        raise HTTPException(
            status_code=400,
            detail=(
                "Missing required fields: "
                "action_id, reconciliation_status"
            ),
        )

    return {
        "acknowledged": True,
        "action_id": action_id,
        "reconciliation_status": reconciliation_status,
    }


@router.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Prometheus metrics endpoint.

    Returns:
        dict: Metrics data.
    """
    return {
        "tickets_created_total": 0,
        "tickets_resolved_total": 0,
        "actions_executed_total": 0,
        "avg_resolution_time_seconds": 0,
    }
