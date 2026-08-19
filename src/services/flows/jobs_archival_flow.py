"""Flow 3: Job vacancy persistent suppression workflow."""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.domain.entities import (
    RiskLevel,
    SupportActionType,
)
from src.infrastructure.m2m.clients import JobsAPIClient
from src.services.approval_service import (
    ApprovalRequest,
    ApprovalService,
)

logger = logging.getLogger(__name__)


class RequesterType(str, Enum):
    """Type of entity requesting job suppression."""

    EMPLOYER = "employer"
    RIGHTS_HOLDER = "rights_holder"
    CANDIDATE = "candidate"


class SuppressionReason(str, Enum):
    """Reason for job suppression."""

    DUPLICATE = "duplicate"
    SPAM = "spam"
    ILLEGAL_CONTENT = "illegal_content"
    FAKE_POSTING = "fake_posting"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    PERSONAL_DATA_VIOLATION = "personal_data_violation"
    OTHER = "other"


class JobsArchivalFlowState(str, Enum):
    """States for jobs archival flow."""

    COLLECT_JOB_DATA = "collect_job_data"
    IDENTIFY_REQUESTER = "identify_requester"
    COLLECT_EVIDENCE = "collect_evidence"
    STAFF_APPROVAL = "staff_approval"
    CALL_JOBS_API = "call_jobs_api"
    COMPLETED = "completed"
    REJECTED = "rejected"


class JobData(BaseModel):
    """Job posting data."""

    job_id: str | None = None
    job_slug: str | None = None
    job_url: str | None = None
    title: str | None = None
    company_id: str | None = None


class ArchivalRequest(BaseModel):
    """Request to archive/suppress a job posting."""

    ticket_id: uuid.UUID
    job_data: JobData
    requester_type: RequesterType
    requester_id: str
    suppression_reason: SuppressionReason
    reason_description: str
    evidence_links: list[str] = Field(default_factory=list)
    evidence_text: str | None = None


class ArchivalContextData(BaseModel):
    """Context data for archival flow."""

    ticket_id: uuid.UUID
    job_id: str | None = None
    job_slug: str | None = None
    job_url: str | None = None
    requester_type: RequesterType
    requester_id: str
    suppression_reason: SuppressionReason
    reason_description: str
    evidence_links: list[str] = Field(default_factory=list)
    evidence_text: str | None = None
    support_action_id: uuid.UUID | None = None
    staff_decision: bool | None = None
    api_response: dict[str, Any] | None = None


class JobsArchivalEngine:
    """Engine for managing job archival/suppression workflow."""

    def __init__(
        self,
        approval_service: ApprovalService,
        jobs_client: JobsAPIClient,
    ) -> None:
        """Initialize jobs archival engine.

        Args:
            approval_service: Approval service for staff decisions.
            jobs_client: Jobs API client for M2M operations.
        """
        self.approval_service = approval_service
        self.jobs_client = jobs_client

    async def create_archival_approval_action(
        self,
        ticket_id: uuid.UUID,
        archival_request: ArchivalRequest,
    ) -> uuid.UUID:
        """Create support action for job archival approval.

        Args:
            ticket_id: Support ticket ID.
            archival_request: Archival request details.

        Returns:
            uuid.UUID: Created action ID.
        """
        # Determine job identifier to use
        job_identifier = (
            archival_request.job_data.job_id
            or archival_request.job_data.job_slug
            or archival_request.job_data.job_url
        )

        approval_request = ApprovalRequest(
            support_ticket_id=ticket_id,
            action_type=SupportActionType.RESOLVE,
            risk_level=RiskLevel.MEDIUM,
            params={
                "job_id": archival_request.job_data.job_id,
                "job_slug": archival_request.job_data.job_slug,
                "job_url": archival_request.job_data.job_url,
                "job_title": archival_request.job_data.title,
                "company_id": archival_request.job_data.company_id,
                "requester_type": archival_request.requester_type.value,
                "requester_id": archival_request.requester_id,
                "suppression_reason": archival_request.suppression_reason.value,
                "reason_description": archival_request.reason_description,
                "evidence_links": archival_request.evidence_links,
                "evidence_text": archival_request.evidence_text,
            },
            idempotency_key=f"archive_job_{job_identifier}_{uuid.uuid4()}",
        )

        action = await self.approval_service.create_support_action(
            approval_request
        )

        logger.info(
            f"Created job archival approval action {action.id} "
            f"for job {job_identifier}"
        )

        return action.id

    async def suppress_job_posting(
        self,
        job_id: str,
        action_id: uuid.UUID,
        requester_id: str,
        suppression_reason: str,
        reason_description: str,
        suppress_source: bool = True,
        suppress_company: bool = False,
        allow_reactivation: bool = False,
    ) -> dict[str, Any]:
        """Suppress job posting in Jobs API with persistent suppression.

        This ensures the job won't be re-indexed by the parser.
        The suppression includes metadata that prevents reactivation.

        Args:
            job_id: Job ID to suppress.
            action_id: Support action ID (for audit trail).
            requester_id: Staff ID who approved the suppression.
            suppression_reason: Reason for suppression.
            reason_description: Detailed reason description.
            suppress_source: Whether to suppress the source (parser).
            suppress_company: Whether to suppress all jobs from this company.
            allow_reactivation: Whether job can be reactivated later.

        Returns:
            dict: Response from Jobs API.

        Raises:
            RuntimeError: If suppression fails.
        """
        try:
            response = await self.jobs_client.execute_action(
                action_id=action_id,
                action_type="suppress_job",
                payload={
                    "job_id": job_id,
                    "suppressed_at": datetime.utcnow().isoformat(),
                    "suppression_reason": suppression_reason,
                    "reason_description": reason_description,
                    "ticket_id": str(action_id),
                    "suppressed_by": requester_id,
                    "suppress_source": suppress_source,
                    "suppress_company": suppress_company,
                    "allow_reactivation": allow_reactivation,
                },
                idempotency_key=f"suppress_{job_id}_{action_id}",
            )

            success = response.get("success", False)
            if success:
                logger.info(f"Job {job_id} successfully suppressed")
            else:
                logger.error(
                    f"Job suppression failed for {job_id}: "
                    f"{response.get('error', 'Unknown error')}"
                )
                raise RuntimeError(
                    f"Jobs API returned failure: {response.get('error')}"
                )

            return response

        except Exception as e:
            logger.error(f"Error suppressing job {job_id}: {e}")
            raise RuntimeError(f"Failed to suppress job: {e}")


class JobsArchivalOrchestrator:
    """Orchestrator for job archival flow state transitions."""

    def __init__(self, engine: JobsArchivalEngine) -> None:
        """Initialize orchestrator.

        Args:
            engine: Jobs archival engine.
        """
        self.engine = engine

    async def transition_to_staff_approval(
        self,
        context: ArchivalContextData,
    ) -> uuid.UUID:
        """Transition to STAFF_APPROVAL state.

        Args:
            context: Current flow context.

        Returns:
            uuid.UUID: Support action ID.
        """
        job_data = JobData(
            job_id=context.job_id,
            job_slug=context.job_slug,
            job_url=context.job_url,
        )

        archival_request = ArchivalRequest(
            ticket_id=context.ticket_id,
            job_data=job_data,
            requester_type=context.requester_type,
            requester_id=context.requester_id,
            suppression_reason=context.suppression_reason,
            reason_description=context.reason_description,
            evidence_links=context.evidence_links,
            evidence_text=context.evidence_text,
        )

        action_id = await self.engine.create_archival_approval_action(
            context.ticket_id, archival_request
        )

        return action_id

    async def transition_to_suppress(
        self,
        context: ArchivalContextData,
        suppressed_by: str,
    ) -> dict[str, Any]:
        """Transition to CALL_JOBS_API state (suppress job).

        Args:
            context: Current flow context.
            suppressed_by: Staff ID who approved suppression.

        Returns:
            dict: Jobs API response.
        """
        if not context.support_action_id:
            raise ValueError("Support action ID required for suppression")

        if not context.staff_decision:
            raise ValueError("Staff must approve before suppression")

        if not context.job_id:
            raise ValueError("Job ID required for suppression")

        response = await self.engine.suppress_job_posting(
            job_id=context.job_id,
            action_id=context.support_action_id,
            requester_id=suppressed_by,
            suppression_reason=context.suppression_reason.value,
            reason_description=context.reason_description,
            suppress_source=True,
            suppress_company=False,
            allow_reactivation=False,
        )

        return response
