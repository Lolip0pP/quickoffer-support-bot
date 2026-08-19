"""Telegram handlers for Mode B (LLM Investigation and Human Handoff)."""

import logging
from typing import Any

from aiogram import Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from src.core.config import settings
from src.services.handoff_engine import get_handoff_service
from src.services.identity import check_identity_verified
from src.services.llm_investigation import InvestigationService

logger = logging.getLogger(__name__)

# Router for Mode B handlers
router = Router(name="mode_b")


class ModeB:
    """State management for Mode B investigation."""

    pass


async def handle_mode_b_question(
    message: types.Message,
    state: FSMContext,
) -> None:
    """Handle general questions (Mode B: LLM Investigation).

    This handler processes questions that don't fit deterministic Mode A flows.
    It performs RAG-based investigation with handoff triggers.

    Args:
        message: User message.
        state: FSM context.
    """
    if not message.text:
        await message.reply("Пожалуйста, отправьте текстовое сообщение.")
        return

    user_id = str(message.from_user.id)
    chat_id = message.chat.id
    user_message = message.text

    logger.info(
        f"Mode B question received from user {user_id}: {user_message[:100]}..."
    )

    # Check identity verification (Trigger 2)
    identity_verified = await check_identity_verified(user_id)

    # Initialize services
    investigation_service = InvestigationService()
    handoff_service = get_handoff_service()

    # Prepare context for investigation
    investigation_context = {
        "conversation_id": str(chat_id),
        "user_id": user_id,
        "identity_verified": identity_verified,
    }

    # Step 1: Check for explicit handoff triggers BEFORE investigation
    should_handoff, trigger_type, reason = handoff_service.detector.detect(
        user_message, investigation_context
    )

    if should_handoff:
        logger.info(
            f"Immediate handoff triggered: {trigger_type} - {reason}"
        )
        await _execute_handoff(
            message,
            user_message,
            chat_id,
            user_id,
            handoff_service,
            investigation_context,
            trigger_reason=reason,
            trigger_type=trigger_type,
        )
        return

    # Step 2: Run RAG investigation
    await message.chat.do("typing")
    investigation_context["identity_verified"] = identity_verified

    try:
        investigation_result = await investigation_service.investigate(
            user_message, user_id, investigation_context
        )
    except Exception as e:
        logger.error(f"Investigation service error: {e}")
        handoff_service.record_llm_failure(str(chat_id))
        investigation_result = {
            "answer": None,
            "confidence": 0.0,
            "should_escalate": True,
            "reason": "investigation_error",
        }

    # Step 3: Check if investigation indicates escalation
    if investigation_result.get("should_escalate"):
        logger.info(
            f"Investigation indicated escalation: "
            f"{investigation_result.get('reason')}"
        )
        investigation_context["investigation_summary"] = (
            f"Investigation confidence: {investigation_result.get('confidence', 0):.2f}. "
            f"Reason: {investigation_result.get('reason', 'unknown')}"
        )
        investigation_context[
            "confidence_score"
        ] = investigation_result.get("confidence", 0.0)

        await _execute_handoff(
            message,
            user_message,
            chat_id,
            user_id,
            handoff_service,
            investigation_context,
            trigger_reason=investigation_result.get(
                "reason", "low_confidence"
            ),
            trigger_type=None,
        )
        return

    # Step 4: Send successful response
    answer = investigation_result.get("answer")
    if not answer:
        logger.warning("Investigation returned empty answer despite success flag")
        investigation_context[
            "investigation_summary"
        ] = "Investigation completed but generated empty response."
        investigation_context["confidence_score"] = 0.0
        await _execute_handoff(
            message,
            user_message,
            chat_id,
            user_id,
            handoff_service,
            investigation_context,
            trigger_reason="empty_response",
            trigger_type=None,
        )
        return

    # Format response with sources
    response_text = answer

    sources = investigation_result.get("sources", [])
    if sources:
        response_text += "\n\n📚 <b>Источники:</b>\n"
        for source in sources[:3]:  # Max 3 sources
            response_text += (
                f"  • {source.get('category', 'Info')}: "
                f"{source.get('title', 'Unknown')}\n"
            )

    confidence = investigation_result.get("confidence", 0.0)
    response_text += (
        f"\n\n_Уверенность ответа: {confidence:.0%}_"
    )

    await message.reply(response_text, parse_mode="HTML")

    # Reset failure counters on success
    handoff_service.reset_failures(str(chat_id))

    logger.info(
        f"Mode B investigation completed successfully "
        f"(confidence={confidence:.2f})"
    )


async def _execute_handoff(
    message: types.Message,
    user_message: str,
    chat_id: int,
    user_id: str,
    handoff_service: Any,
    context: dict[str, Any],
    trigger_reason: str,
    trigger_type: str | None = None,
) -> None:
    """Execute handoff to human support.

    Args:
        message: Original user message.
        user_message: User's question text.
        chat_id: Chat/Conversation ID.
        user_id: User ID.
        handoff_service: Handoff service instance.
        context: Investigation context.
        trigger_reason: Reason for escalation.
        trigger_type: Specific trigger type if applicable.
    """
    logger.info(f"Executing handoff for user {user_id}")

    # Send user notification
    notification = (
        "Ваш вопрос требует помощи специалиста. "
        "Сейчас мы создаем заявку в support team. "
        "Ожидайте ответа от оператора."
    )
    await message.reply(notification)

    # Execute handoff in background (don't await to avoid timeout)
    try:
        import uuid
        conversation_id = uuid.UUID(int=chat_id)

        # Determine trigger type if not provided
        if trigger_type is None:
            if "tool_failure" in trigger_reason:
                trigger_type = "tool_failure_cascade"
            elif "llm" in trigger_reason.lower():
                trigger_type = "double_llm_failure"
            else:
                trigger_type = "low_confidence"

        result = await handoff_service.check_and_execute(
            user_message,
            conversation_id,
            user_id,
            context,
        )

        if result["handoff_triggered"]:
            logger.info(
                f"Handoff created: ticket={result['ticket_id']}, "
                f"notification_sent={result['notification_sent']}"
            )
    except Exception as e:
        logger.error(f"Handoff execution error: {e}")


def register_mode_b_handlers(main_router: Router) -> None:
    """Register Mode B handlers with the main router.

    Args:
        main_router: Main application router.
    """
    main_router.include_router(router)
    logger.info("Mode B handlers registered")
