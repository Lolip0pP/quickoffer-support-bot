"""Telegram handlers for staff approval workflow."""

import logging
import uuid
from typing import Any

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.core.config import settings
from src.infrastructure.db.session import get_session
from src.presentation.telegram.repositories import (
    get_action_repository,
    get_audit_repository,
    get_ticket_repository,
)
from src.services.approval_service import (
    ApprovalDecision,
    ApprovalService,
)
from src.services.staff_approval import (
    StaffApprovalEngine,
    StaffRole,
)

logger = logging.getLogger(__name__)

router = Router()


class ApprovalFSM(StatesGroup):
    """FSM states for approval workflow."""

    WAITING_FOR_DECISION = State()
    REQUESTING_INFO = State()


def parse_staff_allowlist(allowlist_json: str) -> dict[str, list[str]]:
    """Parse staff allowlist from JSON string.

    Args:
        allowlist_json: JSON string with staff_id -> roles mapping.

    Returns:
        dict: Parsed allowlist.
    """
    import json

    try:
        return json.loads(allowlist_json)
    except json.JSONDecodeError:
        logger.error("Invalid staff allowlist JSON")
        return {}


# Initialize staff approval engine
staff_allowlist = parse_staff_allowlist(settings.staff_allowlist_json)
approval_engine = StaffApprovalEngine(staff_allowlist)


@router.callback_query(F.data.startswith("approve_"))
async def handle_approve(
    query: types.CallbackQuery, state: FSMContext
) -> None:
    """Handle approve button click.

    Args:
        query: Callback query from Telegram.
        state: FSM context.
    """
    try:
        # Extract action_id from callback data
        action_id_str = query.data.split("_", 1)[1]
        action_id = uuid.UUID(action_id_str)

        # Get staff_id from Telegram user
        staff_id = str(query.from_user.id)

        # Check if staff member can approve
        if not approval_engine.can_approve(staff_id):
            await query.answer(
                "❌ You don't have permission to approve actions",
                show_alert=True,
            )
            return

        # Get repositories
        async with get_session() as session:
            action_repo = get_action_repository(session)
            audit_repo = get_audit_repository(session)

            # Create approval service
            approval_service = ApprovalService(action_repo, audit_repo)

            # Process decision
            decision = ApprovalDecision(
                action_id=action_id,
                approved=True,
                staff_id=staff_id,
            )

            await approval_service.process_approval_decision(decision)

            # Update message
            confirmation = approval_engine.format_decision_confirmation(
                action_id, approved=True, staff_id=staff_id
            )

            await query.message.edit_text(
                f"{query.message.text}\n\n{confirmation}",
                parse_mode="Markdown",
            )

            await query.answer("✅ Action approved")
            logger.info(f"Action {action_id} approved by staff {staff_id}")

    except Exception as e:
        logger.error(f"Error processing approval: {e}")
        await query.answer("❌ Error processing approval", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def handle_reject(
    query: types.CallbackQuery, state: FSMContext
) -> None:
    """Handle reject button click.

    Args:
        query: Callback query from Telegram.
        state: FSM context.
    """
    try:
        # Extract action_id from callback data
        action_id_str = query.data.split("_", 1)[1]
        action_id = uuid.UUID(action_id_str)

        # Get staff_id from Telegram user
        staff_id = str(query.from_user.id)

        # Check if staff member can approve
        if not approval_engine.can_approve(staff_id):
            await query.answer(
                "❌ You don't have permission to reject actions",
                show_alert=True,
            )
            return

        # Set FSM state to request rejection reason
        await state.set_state(ApprovalFSM.REQUESTING_INFO)
        await state.update_data(action_id=action_id, staff_id=staff_id)

        await query.message.reply(
            "Please provide a reason for rejection:",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error processing rejection: {e}")
        await query.answer("❌ Error processing rejection", show_alert=True)


@router.callback_query(F.data.startswith("info_"))
async def handle_request_info(
    query: types.CallbackQuery, state: FSMContext
) -> None:
    """Handle request info button click.

    Args:
        query: Callback query from Telegram.
        state: FSM context.
    """
    try:
        # Extract action_id from callback data
        action_id_str = query.data.split("_", 1)[1]
        action_id = uuid.UUID(action_id_str)

        # Get staff_id from Telegram user
        staff_id = str(query.from_user.id)

        # Check if staff member can approve
        if not approval_engine.can_approve(staff_id):
            await query.answer(
                "❌ You don't have permission to request info",
                show_alert=True,
            )
            return

        # Set FSM state to request additional info
        await state.set_state(ApprovalFSM.REQUESTING_INFO)
        await state.update_data(
            action_id=action_id, staff_id=staff_id, is_info_request=True
        )

        await query.message.reply(
            "Please provide the information you need:",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error processing info request: {e}")
        await query.answer("❌ Error processing request", show_alert=True)


@router.message(ApprovalFSM.REQUESTING_INFO)
async def handle_rejection_reason(
    message: types.Message, state: FSMContext
) -> None:
    """Handle rejection reason or info request.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    try:
        data = await state.get_data()
        action_id = data.get("action_id")
        staff_id = data.get("staff_id")
        is_info_request = data.get("is_info_request", False)

        # Get repositories
        async with get_session() as session:
            action_repo = get_action_repository(session)
            audit_repo = get_audit_repository(session)

            # Create approval service
            approval_service = ApprovalService(action_repo, audit_repo)

            if is_info_request:
                # Log info request to audit log
                from src.domain.entities import AuditLogEntity

                await audit_repo.create(
                    AuditLogEntity(
                        support_action_id=action_id,
                        actor_id=staff_id,
                        target_id=str(action_id),
                        action="info_requested",
                        payload={"info_request": message.text},
                    )
                )

                response = (
                    f"ℹ️ Info request recorded\n\n"
                    f"*Staff:* {staff_id}\n"
                    f"*Request:* {message.text}"
                )
            else:
                # Process rejection decision
                decision = ApprovalDecision(
                    action_id=action_id,
                    approved=False,
                    staff_id=staff_id,
                    reason=message.text,
                )

                await approval_service.process_approval_decision(decision)

                response = approval_engine.format_decision_confirmation(
                    action_id, approved=False, staff_id=staff_id, reason=message.text
                )

            await message.reply(response, parse_mode="Markdown")
            await state.clear()
            logger.info(
                f"Processed decision for action {action_id} from staff {staff_id}"
            )

    except Exception as e:
        logger.error(f"Error processing decision: {e}")
        await message.reply("❌ Error processing your response", parse_mode="Markdown")


async def send_approval_card(
    bot: Any,
    action_id: uuid.UUID,
    ticket_id: uuid.UUID,
    params: dict[str, Any],
    params_hash: str,
    action_type: str,
    risk_level: str,
    created_at: str | None = None,
) -> int | None:
    """Send approval card to staff approval chat.

    Args:
        bot: Telegram bot instance.
        action_id: Action ID.
        ticket_id: Ticket ID.
        params: Action parameters.
        params_hash: Hash of parameters.
        action_type: Type of action.
        risk_level: Risk level.
        created_at: Creation timestamp.

    Returns:
        int: Message ID if sent successfully, None otherwise.
    """
    try:
        import json

        params_str = json.dumps(params, indent=2, ensure_ascii=False)

        message_text = (
            f"📋 *APPROVAL REQUIRED*\n\n"
            f"*Action ID:* `{action_id}`\n"
            f"*Ticket ID:* `{ticket_id}`\n"
            f"*Type:* {action_type}\n"
            f"*Risk Level:* 🔴 {risk_level.upper()}\n"
            f"*Created:* {created_at}\n\n"
            f"*Parameters (frozen):*\n"
            f"```json\n{params_str}\n```\n"
            f"*Hash:* `{params_hash}`\n\n"
            f"⚠️ Any parameter change invalidates this approval."
        )

        # Create inline keyboard with buttons
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="✅ Approve", callback_data=f"approve_{action_id}"
                    ),
                    types.InlineKeyboardButton(
                        text="❌ Reject", callback_data=f"reject_{action_id}"
                    ),
                ],
                [
                    types.InlineKeyboardButton(
                        text="ℹ️ Request Info", callback_data=f"info_{action_id}"
                    ),
                ],
            ]
        )

        message = await bot.send_message(
            chat_id=settings.telegram_approval_chat_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

        logger.info(
            f"Approval card for action {action_id} sent to approval chat"
        )
        return message.message_id

    except Exception as e:
        logger.error(f"Error sending approval card: {e}")
        return None
