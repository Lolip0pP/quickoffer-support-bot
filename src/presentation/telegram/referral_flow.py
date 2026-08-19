"""Referral promo code flow handlers for Telegram bot."""

import logging

from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from src.infrastructure.m2m.fuckhr_client import (
    FuckHRSupportAPIClient,
    FuckHRSupportAPIError,
)
from src.presentation.telegram.handlers import ReferralFlowStates
from src.services.identity import IdentityService, get_identity_service

logger = logging.getLogger(__name__)

referral_router = Router()


@referral_router.message(Command("referral_code"))
async def cmd_referral_code(
    message: types.Message, state: FSMContext
) -> None:
    """Handle /referral_code command - start referral code flow.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    await message.answer(
        "🎁 Getting your referral code...\n\n"
        "Let me verify your QuickOffer account first."
    )
    await state.set_state(ReferralFlowStates.checking_identity)


@referral_router.message(ReferralFlowStates.checking_identity)
async def process_referral_identity_check(
    message: types.Message, state: FSMContext
) -> None:
    """Check identity and process referral code request.

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
            await state.set_state(ReferralFlowStates.generating_code)

            await message.answer(
                "✅ Account verified!\n\n"
                "Generating your referral code..."
            )

            await process_referral_code_generation(message, state)
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
            f"Identity check failed for referral code: {str(e)}",
            extra={"telegram_id": telegram_id},
        )
        await message.answer(
            "❌ Error verifying account. Please try again later."
        )
        await state.clear()


async def process_referral_code_generation(
    message: types.Message, state: FSMContext
) -> None:
    """Generate referral promo code.

    Args:
        message: Telegram message.
        state: FSM context.
    """
    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        await message.answer(
            "❌ Error: User ID not found. Please try /referral_code again."
        )
        await state.clear()
        return

    client = FuckHRSupportAPIClient()

    try:
        response = await client.get_referral_promo_code(user_id)

        code = response.get("code")
        discount = response.get("discount_percent", 15)
        is_new = response.get("is_new", False)

        if not code:
            raise ValueError("No promo code returned from API")

        await state.update_data(promo_code=code)
        await state.set_state(ReferralFlowStates.code_ready)

        status_text = "🆕 New code generated!" if is_new else "♻️ Your existing code"

        await message.answer(
            f"{status_text}\n\n"
            f"📋 Referral Code: `{code}`\n"
            f"💰 Discount: {discount}%\n"
            f"⏱️ Valid: Forever\n\n"
            f"Share this code with friends and they'll get {discount}% off!"
        )

        logger.info(
            f"Referral code generated/retrieved",
            extra={
                "user_id": user_id,
                "code": code,
                "is_new": is_new,
            },
        )

        await state.clear()

    except FuckHRSupportAPIError as e:
        logger.error(
            f"FuckHR API error generating referral code: {str(e)}",
            extra={"user_id": user_id},
        )
        await message.answer(
            "❌ Error generating referral code. Please try again later."
        )
        await state.clear()
    except Exception as e:
        logger.error(
            f"Unexpected error in referral code generation: {str(e)}",
            extra={"user_id": user_id},
        )
        await message.answer(
            "❌ An unexpected error occurred. Please try again later."
        )
        await state.clear()
