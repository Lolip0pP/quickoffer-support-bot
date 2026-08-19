"""Telegram handlers for refund and subscription deletion flow (Flow 1)."""

import logging
import uuid
from typing import Any

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.config import settings
from src.infrastructure.db.session import get_session
from src.infrastructure.m2m import get_fuckhr_client
from src.presentation.telegram.approval_handlers import send_approval_card
from src.presentation.telegram.repositories import (
    get_action_repository,
    get_audit_repository,
    get_ticket_repository,
)
from src.services.approval_service import ApprovalService
from src.services.flows.refund_flow import (
    PaymentInfo,
    RefundBasis,
    RefundContextData,
    RefundFlowEngine,
    RefundFlowOrchestrator,
    RefundFlowState,
)

logger = logging.getLogger(__name__)

router = Router()


class RefundFlowFSM(StatesGroup):
    """FSM states for refund flow."""

    IDENTIFY = State()
    SELECT_PAYMENT = State()
    PREVIEW = State()
    COLLECT_REASON = State()
    CONFIRM = State()
    STAFF_APPROVAL = State()
    REFUND_MANUAL = State()
    VERIFY_REFUND = State()
    SOFT_DELETE = State()
    COMPLETED = State()
    REJECTED = State()


async def format_payment_list(payments: list[PaymentInfo]) -> str:
    """Format list of payments for display.

    Args:
        payments: List of payment info objects.

    Returns:
        str: Formatted payment list.
    """
    if not payments:
        return "❌ No payments found."

    message = "💳 *Your Recent Payments:*\n\n"

    for idx, payment in enumerate(payments, 1):
        message += (
            f"{idx}. *Amount:* {payment.amount} {payment.currency}\n"
            f"   *Date:* {payment.created_at}\n"
            f"   *Status:* {payment.status}\n"
            f"   *ID:* `{payment.payment_id}`\n\n"
        )

    return message


async def format_refund_preview(preview: dict[str, Any]) -> str:
    """Format refund preview for display.

    Args:
        preview: Refund preview data from backend.

    Returns:
        str: Formatted preview message.
    """
    message = "📋 *Refund Preview*\n\n"

    message += f"*Amount to refund:* {preview.get('refund_amount')} {preview.get('currency')}\n"
    message += f"*Status:* {preview.get('status')}\n"
    message += f"*Conditions met:* {'✅ Yes' if preview.get('conditions_met') else '❌ No'}\n\n"

    if not preview.get("conditions_met"):
        message += "⚠️ *Refund Conditions Not Met:*\n"
        for reason in preview.get("reasons", []):
            message += f"  • {reason}\n"
    else:
        message += "✅ *Refund conditions are satisfied.*\n"

    return message


@router.message(F.text == "/refund")
async def start_refund_flow(message: types.Message, state: FSMContext) -> None:
    """Start refund flow.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    user_id = str(message.from_user.id)

    await state.set_state(RefundFlowFSM.IDENTIFY)
    await state.update_data(user_id=user_id)

    await message.reply(
        "🔄 *Refund & Subscription Deletion*\n\n"
        "I'll help you request a refund. Let me show you your recent payments.\n"
        "Please wait...",
        parse_mode="Markdown",
    )

    try:
        # Get user payments from FuckHR API
        async with get_session() as session:
            fuckhr_client = get_fuckhr_client()
            approval_service = ApprovalService(
                get_action_repository(session), get_audit_repository(session)
            )

            engine = RefundFlowEngine(approval_service, fuckhr_client)
            payments = await engine.get_user_payments(user_id)

            payment_list_text = await format_payment_list(payments)

            # Store payments in context
            await state.update_data(
                payments=[
                    {
                        "payment_id": p.payment_id,
                        "amount": p.amount,
                        "currency": p.currency,
                        "created_at": p.created_at,
                        "status": p.status,
                    }
                    for p in payments
                ]
            )

            await state.set_state(RefundFlowFSM.SELECT_PAYMENT)

            await message.reply(
                payment_list_text + "\n\nReply with the payment number (1-5) you want to refund:",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Error retrieving payments: {e}")
        await message.reply(
            "❌ Error retrieving your payments. Please try again later.",
            parse_mode="Markdown",
        )
        await state.clear()


@router.message(RefundFlowFSM.SELECT_PAYMENT)
async def select_payment(message: types.Message, state: FSMContext) -> None:
    """Handle payment selection.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    try:
        payment_idx = int(message.text) - 1
        data = await state.get_data()
        payments = data.get("payments", [])

        if payment_idx < 0 or payment_idx >= len(payments):
            await message.reply("❌ Invalid payment number. Please try again.")
            return

        selected_payment = payments[payment_idx]
        await state.update_data(
            payment_id=selected_payment["payment_id"],
            amount=selected_payment["amount"],
            currency=selected_payment["currency"],
        )

        # Get refund preview
        async with get_session() as session:
            fuckhr_client = get_fuckhr_client()
            approval_service = ApprovalService(
                get_action_repository(session), get_audit_repository(session)
            )

            engine = RefundFlowEngine(approval_service, fuckhr_client)
            preview = await engine.get_refund_preview(
                user_id=data["user_id"],
                payment_id=selected_payment["payment_id"],
                refund_basis=RefundBasis.SERVICE_NOT_STARTED,
            )

            preview_text = await format_refund_preview(preview)
            await message.reply(preview_text, parse_mode="Markdown")

            await state.set_state(RefundFlowFSM.COLLECT_REASON)
            await message.reply(
                "📝 *Refund Reason*\n\n"
                "Please select the reason for refund:\n"
                "1. Service not started\n"
                "2. Double charge / Duplicate payment\n"
                "3. Erroneous charge\n"
                "4. QuickOffer error\n\n"
                "Reply with the reason number (1-4):",
                parse_mode="Markdown",
            )

    except (ValueError, IndexError):
        await message.reply("❌ Invalid input. Please enter a number between 1-5.")
    except Exception as e:
        logger.error(f"Error selecting payment: {e}")
        await message.reply(
            "❌ Error processing your selection. Please try again.",
            parse_mode="Markdown",
        )
        await state.clear()


@router.message(RefundFlowFSM.COLLECT_REASON)
async def collect_reason(message: types.Message, state: FSMContext) -> None:
    """Collect refund reason and evidence.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    reason_map = {
        "1": RefundBasis.SERVICE_NOT_STARTED,
        "2": RefundBasis.DOUBLE_CHARGE,
        "3": RefundBasis.ERRONEOUS_CHARGE,
        "4": RefundBasis.QUICKOFFER_ERROR,
    }

    if message.text not in reason_map:
        await message.reply("❌ Invalid reason. Please enter a number between 1-4.")
        return

    refund_basis = reason_map[message.text]
    await state.update_data(refund_basis=refund_basis.value)

    await state.set_state(RefundFlowFSM.CONFIRM)
    await message.reply(
        "📸 *Evidence*\n\n"
        "Please provide any evidence supporting your refund request "
        "(screenshots, links, etc.). You can share multiple files/links.\n\n"
        "When done, reply with *confirm*.",
        parse_mode="Markdown",
    )


@router.message(RefundFlowFSM.CONFIRM)
async def confirm_refund(message: types.Message, state: FSMContext) -> None:
    """Confirm refund request and send to staff approval.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    if message.text.lower() != "confirm":
        # Collect evidence
        data = await state.get_data()
        evidence_links = data.get("evidence_links", [])

        if message.text.startswith("http"):
            evidence_links.append(message.text)
            await state.update_data(evidence_links=evidence_links)
            await message.reply(f"✅ Evidence saved ({len(evidence_links)} item(s))")
        else:
            await state.update_data(evidence_text=message.text)
            await message.reply("✅ Description saved\n\nReply with *confirm* when ready.")

        return

    # Process confirmation
    try:
        data = await state.get_data()

        # Create ticket and action for approval
        async with get_session() as session:
            ticket_repo = get_ticket_repository(session)
            action_repo = get_action_repository(session)
            audit_repo = get_audit_repository(session)
            fuckhr_client = get_fuckhr_client()

            approval_service = ApprovalService(action_repo, audit_repo)
            engine = RefundFlowEngine(approval_service, fuckhr_client)

            # Create support ticket
            from src.domain.entities import (
                SupportTicketEntity,
                SupportTicketState,
            )

            conversation_id = uuid.uuid4()  # Should come from context
            ticket = await ticket_repo.create(
                SupportTicketEntity(
                    conversation_id=conversation_id,
                    flow_type="refund",
                    state=SupportTicketState.IN_PROGRESS,
                    metadata={
                        "user_id": data["user_id"],
                        "payment_id": data["payment_id"],
                    },
                )
            )

            # Create refund action
            from src.services.flows.refund_flow import RefundRequest

            refund_request = RefundRequest(
                user_id=data["user_id"],
                ticket_id=ticket.id,
                payment_id=data["payment_id"],
                amount=data["amount"],
                currency=data["currency"],
                refund_basis=RefundBasis(data["refund_basis"]),
                reason=data.get("evidence_text", "User requested refund"),
                evidence_links=data.get("evidence_links", []),
            )

            action_id = await engine.create_refund_approval_action(
                ticket.id, refund_request
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
                params=refund_request.dict(),
                params_hash="",  # Will be set by approval service
                action_type="refund",
                risk_level="high",
            )

            await state.set_state(RefundFlowFSM.STAFF_APPROVAL)
            await message.reply(
                "✅ *Refund Request Submitted*\n\n"
                "Your refund request has been sent to our support team for review.\n"
                "Staff will review the evidence and make a decision.\n\n"
                "You'll be notified once a decision is made.",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Error confirming refund: {e}")
        await message.reply(
            "❌ Error submitting refund request. Please try again.",
            parse_mode="Markdown",
        )
        await state.clear()


@router.message(RefundFlowFSM.REFUND_MANUAL)
async def collect_provider_refund_id(
    message: types.Message, state: FSMContext
) -> None:
    """Collect provider refund ID from staff after manual refund in YooKassa.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    try:
        provider_refund_id = message.text.strip()

        if not provider_refund_id:
            await message.reply("❌ Please provide a valid refund ID.")
            return

        # Verify refund in provider
        data = await state.get_data()

        async with get_session() as session:
            fuckhr_client = get_fuckhr_client()
            approval_service = ApprovalService(
                get_action_repository(session), get_audit_repository(session)
            )

            engine = RefundFlowEngine(approval_service, fuckhr_client)

            is_verified = await engine.verify_provider_refund(
                payment_id=data["payment_id"],
                provider_refund_id=provider_refund_id,
            )

            if not is_verified:
                await message.reply(
                    "❌ Refund verification failed. Please check the refund ID.",
                    parse_mode="Markdown",
                )
                return

            await state.update_data(
                provider_refund_id=provider_refund_id,
                refund_verified=True,
            )

            # Soft delete subscription
            await state.set_state(RefundFlowFSM.SOFT_DELETE)

            success = await engine.soft_delete_subscription(
                user_id=data["user_id"],
                action_id=uuid.UUID(data["support_action_id"]),
            )

            if success:
                await state.set_state(RefundFlowFSM.COMPLETED)
                await message.reply(
                    "✅ *Refund Completed*\n\n"
                    "Your refund has been processed and your subscription has been deleted.\n"
                    "All active searches and auto-renewal have been disabled.",
                    parse_mode="Markdown",
                )
            else:
                await state.set_state(RefundFlowFSM.COMPLETED)
                await message.reply(
                    "⚠️ *Refund Processed with Partial Success*\n\n"
                    "Your refund was successful, but subscription deletion encountered an issue.\n"
                    "Our team will resolve this shortly.",
                    parse_mode="Markdown",
                )

            await state.clear()

    except Exception as e:
        logger.error(f"Error verifying provider refund: {e}")
        await message.reply(
            "❌ Error processing refund. Please contact support.",
            parse_mode="Markdown",
        )
        await state.clear()
