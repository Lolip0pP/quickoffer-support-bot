"""Review promo code flow handlers for Telegram bot."""

import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.infrastructure.m2m.fuckhr_client import (
    FuckHRSupportAPIClient,
    FuckHRSupportAPIError,
)
from src.presentation.telegram.handlers import ReviewFlowStates
from src.services.identity import get_identity_service

logger = logging.getLogger(__name__)

review_router = Router()


@review_router.message(Command("review_promo"))
async def cmd_review_promo(
    message: types.Message, state: FSMContext
) -> None:
    """Handle /review_promo command - start review promo code flow.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    await message.answer(
        "⭐ Get a promo code for your review!\n\n"
        "Let me verify your QuickOffer account first."
    )
    await state.set_state(ReviewFlowStates.checking_identity)


@review_router.message(ReviewFlowStates.checking_identity)
async def process_review_identity_check(
    message: types.Message, state: FSMContext
) -> None:
    """Check identity and proceed to review check.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    telegram_id = message.from_user.id if message.from_user else 0

    identity_service = get_identity_service()

    try:
        result = await identity_service.check_and_bind_or_link(
            telegram_id
        )

        if "user_id" in result:
            await state.update_data(user_id=result["user_id"])
            await state.set_state(ReviewFlowStates.checking_review)

            await message.answer(
                "✅ Account verified!\n\n"
                "Checking for your reviews..."
            )

            await process_review_check(message, state)
        else:
            await message.answer(
                "🔗 Your Telegram account is not yet linked to QuickOffer.\n\n"
                f"Please click the link below to bind your account:\n\n"
                f"{result.get('auth_url', 'N/A')}\n\n"
                f"⏰ Link expires in 1 hour"
            )
            await state.clear()

    except Exception as e:
        logger.error(
            f"Identity check failed for review promo: {str(e)}",
            extra={"telegram_id": telegram_id},
        )
        await message.answer(
            "❌ Error verifying account. Please try again later."
        )
        await state.clear()


async def process_review_check(
    message: types.Message, state: FSMContext
) -> None:
    """Check if user has published review.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        await message.answer(
            "❌ Error: User ID not found. Please try /review_promo again."
        )
        await state.clear()
        return

    client = FuckHRSupportAPIClient()

    try:
        review_response = await client.check_review(user_id)
        review_found = review_response.get("review_found", False)

        if review_found:
            await state.update_data(
                review_id=review_response.get("review_id"),
                review_found=True,
            )
            await state.set_state(ReviewFlowStates.generating_code)

            await message.answer(
                "🎉 Great! We found your review.\n\n"
                "Generating your promo code..."
            )

            await process_review_promo_generation(message, state)
        else:
            await state.update_data(review_found=False)
            await state.set_state(ReviewFlowStates.sending_form)

            form_response = await client.get_review_form_url()
            form_url = form_response.get("review_form_url", "#")

            await message.answer(
                "📝 We don't have a review from you yet.\n\n"
                f"Please share your feedback using this link:\n\n"
                f"{form_url}\n\n"
                f"📌 Note: After submitting, your review will be processed. "
                f"Then you can request the promo code again!"
            )

            await state.clear()

    except FuckHRSupportAPIError as e:
        logger.error(
            f"FuckHR API error checking review: {str(e)}",
            extra={"user_id": user_id},
        )
        await message.answer(
            "❌ Error checking your review. Please try again later."
        )
        await state.clear()
    except Exception as e:
        logger.error(
            f"Unexpected error in review check: {str(e)}",
            extra={"user_id": user_id},
        )
        await message.answer(
            "❌ An unexpected error occurred. Please try again later."
        )
        await state.clear()


async def process_review_promo_generation(
    message: types.Message, state: FSMContext
) -> None:
    """Generate one-time review promo code.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    data = await state.get_data()
    user_id = data.get("user_id")
    review_id = data.get("review_id")

    if not user_id:
        await message.answer(
            "❌ Error: User ID not found. Please try /review_promo again."
        )
        await state.clear()
        return

    client = FuckHRSupportAPIClient()

    try:
        response = await client.get_review_promo_code(user_id)

        code = response.get("code")
        discount = response.get("discount_percent", 15)
        max_uses = response.get("max_uses", 1)
        is_new = response.get("is_new", False)
        user_bound = response.get("user_bound", True)

        if not code:
            raise ValueError("No promo code returned from API")

        await state.update_data(promo_code=code)
        await state.set_state(ReviewFlowStates.code_ready)

        status_text = "🆕 New code generated!" if is_new else "♻️ Your existing code"

        await message.answer(
            f"{status_text}\n\n"
            f"📋 Promo Code: `{code}`\n"
            f"💰 Discount: {discount}%\n"
            f"📌 Uses: {max_uses} (one-time)\n"
            f"👤 Account-bound: Yes\n\n"
            f"This code is exclusively for you and can only be used once. "
            f"Thank you for your review!"
        )

        logger.info(
            f"Review promo code generated/retrieved",
            extra={
                "user_id": user_id,
                "review_id": review_id,
                "code": code,
                "is_new": is_new,
            },
        )

        await state.clear()

    except FuckHRSupportAPIError as e:
        logger.error(
            f"FuckHR API error generating review promo: {str(e)}",
            extra={"user_id": user_id, "review_id": review_id},
        )
        await message.answer(
            "❌ Error generating promo code. Please try again later."
        )
        await state.clear()
    except Exception as e:
        logger.error(
            f"Unexpected error in review promo generation: {str(e)}",
            extra={"user_id": user_id, "review_id": review_id},
        )
        await message.answer(
            "❌ An unexpected error occurred. Please try again later."
        )
        await state.clear()
