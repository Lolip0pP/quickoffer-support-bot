"""Telegram handlers for job vacancy archival/suppression flow (Flow 3)."""

import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.config import settings
from src.infrastructure.db.session import get_session
from src.infrastructure.m2m import get_jobs_client
from src.presentation.telegram.approval_handlers import send_approval_card
from src.presentation.telegram.repositories import (
    get_action_repository,
    get_audit_repository,
    get_ticket_repository,
)
from src.services.approval_service import ApprovalService
from src.services.flows.jobs_archival_flow import (
    ArchivalContextData,
    JobsArchivalEngine,
    JobsArchivalFlowState,
    RequesterType,
    SuppressionReason,
)

logger = logging.getLogger(__name__)

router = Router()


class JobsArchivalFSM(StatesGroup):
    """FSM states for jobs archival flow."""

    COLLECT_JOB_DATA = State()
    IDENTIFY_REQUESTER = State()
    COLLECT_EVIDENCE = State()
    STAFF_APPROVAL = State()
    COMPLETED = State()
    REJECTED = State()


REQUESTER_TYPE_MAP = {
    "1": RequesterType.EMPLOYER,
    "2": RequesterType.RIGHTS_HOLDER,
    "3": RequesterType.CANDIDATE,
}

SUPPRESSION_REASON_MAP = {
    "1": SuppressionReason.DUPLICATE,
    "2": SuppressionReason.SPAM,
    "3": SuppressionReason.ILLEGAL_CONTENT,
    "4": SuppressionReason.FAKE_POSTING,
    "5": SuppressionReason.INTELLECTUAL_PROPERTY,
    "6": SuppressionReason.PERSONAL_DATA_VIOLATION,
    "7": SuppressionReason.OTHER,
}


@router.message(F.text == "/archive_job")
async def start_archival_flow(message: types.Message, state: FSMContext) -> None:
    """Start job archival flow.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    user_id = str(message.from_user.id)

    await state.set_state(JobsArchivalFSM.COLLECT_JOB_DATA)
    await state.update_data(requester_id=user_id)

    await message.reply(
        "🗑️ *Job Vacancy Archival Request*\n\n"
        "I'll help you request permanent suppression of a job posting.\n\n"
        "Please provide the job details:\n"
        "- Job URL/slug (e.g., job-id-123 or https://quickoffer.com/jobs/123)\n\n"
        "Send the job identifier:",
        parse_mode="Markdown",
    )


@router.message(JobsArchivalFSM.COLLECT_JOB_DATA)
async def collect_job_data(message: types.Message, state: FSMContext) -> None:
    """Collect job data and identifier.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    job_input = message.text.strip()

    # Parse job identifier
    job_id = None
    job_slug = None
    job_url = None

    if job_input.startswith("http"):
        job_url = job_input
        # Try to extract ID from URL
        if "jobs/" in job_input:
            job_id = job_input.split("jobs/")[-1].split("?")[0]
    elif job_input.isdigit():
        job_id = job_input
    else:
        job_slug = job_input

    await state.update_data(
        job_id=job_id, job_slug=job_slug, job_url=job_url
    )

    await state.set_state(JobsArchivalFSM.IDENTIFY_REQUESTER)

    await message.reply(
        "🔍 *Who is requesting this archival?*\n\n"
        "1. Employer / Job Poster\n"
        "2. Rights Holder / Copyright Owner\n"
        "3. Candidate / User\n\n"
        "Reply with your role number (1-3):",
        parse_mode="Markdown",
    )


@router.message(JobsArchivalFSM.IDENTIFY_REQUESTER)
async def identify_requester(message: types.Message, state: FSMContext) -> None:
    """Identify the type of requester.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    if message.text not in REQUESTER_TYPE_MAP:
        await message.reply("❌ Invalid selection. Please enter 1, 2, or 3.")
        return

    requester_type = REQUESTER_TYPE_MAP[message.text]
    await state.update_data(requester_type=requester_type.value)

    await state.set_state(JobsArchivalFSM.COLLECT_EVIDENCE)

    await message.reply(
        "📋 *Reason for Suppression*\n\n"
        "1. Duplicate posting\n"
        "2. Spam / Invalid posting\n"
        "3. Illegal content\n"
        "4. Fake/Fraudulent posting\n"
        "5. Intellectual property violation\n"
        "6. Personal data violation\n"
        "7. Other reason\n\n"
        "Reply with the reason number (1-7):",
        parse_mode="Markdown",
    )


@router.message(JobsArchivalFSM.COLLECT_EVIDENCE)
async def collect_evidence(message: types.Message, state: FSMContext) -> None:
    """Collect suppression reason and evidence.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    if message.text not in SUPPRESSION_REASON_MAP:
        await message.reply("❌ Invalid reason. Please enter a number between 1-7.")
        return

    reason = SUPPRESSION_REASON_MAP[message.text]
    await state.update_data(suppression_reason=reason.value)

    await message.reply(
        "📸 *Evidence / Justification*\n\n"
        "Please provide details and evidence supporting your request:\n"
        "- Description of why the job should be suppressed\n"
        "- Links to related postings (if applicable)\n"
        "- Screenshots or other proof\n\n"
        "When you're done providing evidence, reply with *proceed* to submit.",
        parse_mode="Markdown",
    )


@router.message(F.text.lower() == "proceed")
async def proceed_to_approval(message: types.Message, state: FSMContext) -> None:
    """Process archival request and send to staff approval.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    try:
        data = await state.get_data()

        # Create ticket and action for approval
        async with get_session() as session:
            ticket_repo = get_ticket_repository(session)
            action_repo = get_action_repository(session)
            audit_repo = get_audit_repository(session)
            jobs_client = get_jobs_client()

            approval_service = ApprovalService(action_repo, audit_repo)
            engine = JobsArchivalEngine(approval_service, jobs_client)

            # Create support ticket
            from src.domain.entities import (
                SupportTicketEntity,
                SupportTicketState,
            )

            conversation_id = uuid.uuid4()  # Should come from context
            ticket = await ticket_repo.create(
                SupportTicketEntity(
                    conversation_id=conversation_id,
                    flow_type="jobs_archival",
                    state=SupportTicketState.IN_PROGRESS,
                    metadata={
                        "job_id": data.get("job_id"),
                        "job_slug": data.get("job_slug"),
                        "requester_id": data.get("requester_id"),
                    },
                )
            )

            # Create archival action
            from src.services.flows.jobs_archival_flow import (
                ArchivalRequest,
                JobData,
            )

            job_data = JobData(
                job_id=data.get("job_id"),
                job_slug=data.get("job_slug"),
                job_url=data.get("job_url"),
            )

            archival_request = ArchivalRequest(
                ticket_id=ticket.id,
                job_data=job_data,
                requester_type=RequesterType(data["requester_type"]),
                requester_id=data["requester_id"],
                suppression_reason=SuppressionReason(data["suppression_reason"]),
                reason_description=data.get("reason_description", ""),
                evidence_links=data.get("evidence_links", []),
                evidence_text=data.get("evidence_text", ""),
            )

            action_id = await engine.create_archival_approval_action(
                ticket.id, archival_request
            )

            await state.update_data(
                ticket_id=str(ticket.id),
                support_action_id=str(action_id),
            )

            # Send approval card to staff
            await send_approval_card(
                bot=None,  # Should come from context
                action_id=action_id,
                ticket_id=ticket.id,
                params=archival_request.dict(),
                params_hash="",  # Will be set by approval service
                action_type="job_archival",
                risk_level="medium",
            )

            await state.set_state(JobsArchivalFSM.STAFF_APPROVAL)

            await message.reply(
                "✅ *Archival Request Submitted*\n\n"
                "Your job archival request has been sent to our support team.\n"
                "Staff will review the evidence and make a decision.\n\n"
                "Once approved, the job will be permanently suppressed and won't appear in searches.",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Error submitting archival request: {e}")
        await message.reply(
            "❌ Error submitting your request. Please try again.",
            parse_mode="Markdown",
        )
        await state.clear()


@router.message(
    JobsArchivalFSM.COLLECT_EVIDENCE,
)
async def collect_evidence_details(
    message: types.Message, state: FSMContext
) -> None:
    """Collect additional evidence details.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    data = await state.get_data()
    evidence_links = data.get("evidence_links", [])

    if message.text.startswith("http"):
        evidence_links.append(message.text)
        await state.update_data(evidence_links=evidence_links)
        await message.reply(f"✅ Link saved ({len(evidence_links)} item(s))")
    else:
        await state.update_data(evidence_text=message.text)
        await message.reply(
            "✅ Evidence received.\n\nReply with *proceed* to submit your request."
        )
