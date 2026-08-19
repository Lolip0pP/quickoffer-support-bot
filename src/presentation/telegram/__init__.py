"""Telegram handlers module - aiogram v3 integration."""

from src.presentation.telegram.handlers import (
    ReferralFlowStates,
    ReviewFlowStates,
    SupportFlowStates,
    router,
)
from src.presentation.telegram.referral_flow import referral_router
from src.presentation.telegram.review_flow import review_router

__all__ = [
    "router",
    "referral_router",
    "review_router",
    "SupportFlowStates",
    "ReferralFlowStates",
    "ReviewFlowStates",
]
