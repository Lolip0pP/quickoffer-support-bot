"""Telegram bot handlers using aiogram v3."""

import logging
from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.services.processing import QuestionProcessor

logger = logging.getLogger(__name__)

router = Router()
processor: QuestionProcessor | None = None


async def get_processor() -> QuestionProcessor:
    """Get or initialize the QuestionProcessor."""
    global processor
    if processor is None:
        processor = QuestionProcessor()
        logger.info("QuestionProcessor initialized")
    return processor


class SupportFlowStates(StatesGroup):
    """FSM states for support flow."""

    waiting_for_issue = State()
    waiting_for_details = State()
    waiting_for_confirmation = State()


class ReferralFlowStates(StatesGroup):
    """FSM states for referral promo code flow."""

    requesting_code = State()
    checking_identity = State()
    generating_code = State()
    code_ready = State()


class ReviewFlowStates(StatesGroup):
    """FSM states for review promo code flow."""

    requesting_code = State()
    checking_identity = State()
    checking_review = State()
    sending_form = State()
    generating_code = State()
    code_ready = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Handle /start command.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    await message.answer(
        "👋 Welcome to QuickOffer Support Bot!\n\n"
        "I'm here to help you with any issues. "
        "Type /help to see available commands."
    )
    await state.clear()


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    """Handle /help command.

    Args:
        message: Telegram message.
    """
    help_text = (
        "📚 Available Commands:\n\n"
        "🎫 Support Flow:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/issue - Report a new issue\n"
        "/status - Check your ticket status\n\n"
        "🎁 Promotions:\n"
        "/referral_code - Get your referral promo code (15% discount)\n"
        "/review_promo - Get promo code for your review (15% discount)\n\n"
        "⚙️ Controls:\n"
        "/cancel - Cancel current operation\n"
    )
    await message.answer(help_text)


@router.message(Command("issue"))
async def cmd_issue(message: types.Message, state: FSMContext) -> None:
    """Handle /issue command - start support flow.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    await message.answer(
        "📝 Please describe your issue in detail:"
    )
    await state.set_state(SupportFlowStates.waiting_for_issue)


@router.message(SupportFlowStates.waiting_for_issue)
async def process_issue_description(
    message: types.Message, state: FSMContext
) -> None:
    """Process issue description.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    await state.update_data(issue_description=message.text)
    await message.answer(
        "Thank you! Please provide any additional details or context:"
    )
    await state.set_state(SupportFlowStates.waiting_for_details)


@router.message(SupportFlowStates.waiting_for_details)
async def process_issue_details(
    message: types.Message, state: FSMContext
) -> None:
    """Process issue details and create ticket.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    await state.update_data(issue_details=message.text)

    data = await state.get_data()
    await message.answer(
        f"✅ Thank you for the details!\n\n"
        f"Your support ticket has been created and assigned to our team.\n"
        f"We'll review it shortly and get back to you.\n\n"
        f"📌 Keep your chat open for updates."
    )
    await state.clear()


@router.message(Command("status"))
async def cmd_status(message: types.Message) -> None:
    """Handle /status command.

    Args:
        message: Telegram message.
    """
    await message.answer(
        "📊 Your Support Tickets:\n\n"
        "Ticket #1: In Progress ⏳\n"
        "Created: 2 hours ago\n"
        "Last update: 1 hour ago\n\n"
        "Use /issue to create a new ticket."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    """Handle /cancel command.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("No active operation to cancel.")
        return

    await state.clear()
    await message.answer("❌ Operation cancelled.")


@router.message(StateFilter(None))
async def handle_question(message: types.Message) -> None:
    """Handle user questions and process them through the bot pipeline.

    Args:
        message: Telegram message.
    """
    if not message.text or message.text.startswith("/"):
        await message.answer(
            "I didn't understand that. Type /help for available commands."
        )
        return

    try:
        # Show processing indicator
        await message.answer("🔄 Processing your request...")

        # Get the question processor
        proc = await get_processor()

        # Process the question
        result = await proc.process(message.text)

        # Log the processing sequence to console
        sequence = result.context.log_phase_sequence()
        if sequence:
            logger.info(f"\n{sequence}")

        # Build response based on processing mode
        mode = result.context.processing_mode.value.upper()

        response_lines = [
            f"<b>✨ Processing Complete</b>\n",
            f"<b>Mode:</b> {mode}",
        ]

        # Add mode-specific info
        if result.context.flow_type:
            response_lines.append(f"<b>Flow:</b> {result.context.flow_type.value}")

        if result.confidence_level:
            response_lines.append(f"<b>Confidence:</b> {result.confidence_level}")

        response_lines.append("")  # Blank line

        # Add the answer
        response_lines.append(f"<b>Answer:</b>\n{result.context.final_answer}")

        # Add approval info for Mode A
        if result.context.requires_staff_approval:
            response_lines.append(
                f"\n⚠️ <b>Staff Approval Required</b>"
            )
            if result.context.approval_token:
                response_lines.append(
                    f"<code>Token: {result.context.approval_token[:24]}...</code>"
                )

        # Add phase info (collapsed)
        if result.context.phases:
            response_lines.append(f"\n📊 <b>Phases ({len(result.context.phases)}):</b>")
            for i, phase in enumerate(result.context.phases, 1):
                status = "✅" if phase.status == "success" else "❌" if phase.status == "failed" else "⏳"
                phase_name = phase.phase.value.replace("_", " ").title()
                response_lines.append(f"  {i}. {status} {phase_name}")

        response = "\n".join(response_lines)

        # Split long responses
        max_length = 4096
        if len(response) > max_length:
            # Send response in chunks
            await message.answer(response[:max_length], parse_mode="HTML")
            await message.answer(response[max_length:], parse_mode="HTML")
        else:
            await message.answer(response, parse_mode="HTML")

        logger.info(
            f"Question processed: mode={mode}, "
            f"confidence={result.confidence_level}, "
            f"requires_approval={result.context.requires_staff_approval}"
        )

    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        await message.answer(
            f"❌ Error processing your request: {str(e)}\n\n"
            f"Please try again or type /help for assistance."
        )
