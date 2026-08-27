"""Intent router - classifies questions into MODE_A (deterministic flows) or MODE_B (investigation)."""

import logging
from typing import Optional

from src.benchmarking.flow_matcher import FlowMatcher
from src.benchmarking.processing_phases import (
    FlowType,
    ProcessingContext,
    ProcessingMode,
    ToolCall,
)

logger = logging.getLogger(__name__)


class IntentRouter:
    """Routes questions to MODE_A (deterministic flows) or MODE_B (LLM investigation)."""

    # Mapping from flow_matcher flow names to our FlowType + tools
    FLOW_DEFINITIONS = {
        "return_refund": {
            "flow_type": FlowType.REFUND,
            "mode": ProcessingMode.MODE_A_DETERMINISTIC,
            "requires_approval": True,
            "tools": [
                ToolCall(
                    tool_name="fuckhr-api/GetUserPayments",
                    tool_type="backend_api",
                    description="Retrieve user payment history",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/GetRefundPreview",
                    tool_type="backend_api",
                    description="Get refund eligibility and preview",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/ValidateRefundBasis",
                    tool_type="backend_api",
                    description="Validate refund basis (service not started, double charge, etc.)",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="YooKassa/ProcessRefund",
                    tool_type="backend_api",
                    description="Process refund in payment provider (manual staff action)",
                    requires_approval=True,
                ),
                ToolCall(
                    tool_name="fuckhr-api/RevokeSubscription",
                    tool_type="backend_api",
                    description="Soft-delete subscription (deactivate searches, revoke auto-renewal)",
                    requires_approval=True,
                ),
            ],
        },
        "career_assistance": {
            "flow_type": FlowType.CAREER_HELP,
            "mode": ProcessingMode.MODE_A_DETERMINISTIC,
            "requires_approval": False,
            "tools": [
                ToolCall(
                    tool_name="fuckhr-api/CheckEligibility",
                    tool_type="backend_api",
                    description="Check career help eligibility (Premium 14d, discount <16%)",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/CreateCareerTicket",
                    tool_type="backend_api",
                    description="Create support ticket for career assistance team",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="internal-telegram/SendToCareerChat",
                    tool_type="backend_api",
                    description="Route ticket to career help team chat with SLA",
                    requires_approval=False,
                ),
            ],
        },
        "job_archival": {
            "flow_type": FlowType.JOB_ARCHIVAL,
            "mode": ProcessingMode.MODE_A_DETERMINISTIC,
            "requires_approval": True,
            "tools": [
                ToolCall(
                    tool_name="jobs-api/LookupJob",
                    tool_type="backend_api",
                    description="Lookup job vacancy by URL/slug",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="jobs-api/PersistentSuppress",
                    tool_type="backend_api",
                    description="Persistently suppress job (prevent re-indexing and reactivation)",
                    requires_approval=True,
                ),
                ToolCall(
                    tool_name="jobs-api/VerifySuppressionStatus",
                    tool_type="backend_api",
                    description="Verify suppression was applied successfully",
                    requires_approval=False,
                ),
            ],
        },
        "referral_promo": {
            "flow_type": FlowType.REFERRAL_PROMO,
            "mode": ProcessingMode.MODE_A_DETERMINISTIC,
            "requires_approval": False,
            "tools": [
                ToolCall(
                    tool_name="fuckhr-api/CheckReferralOwnership",
                    tool_type="backend_api",
                    description="Check if user already has referral code",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/GenerateReferralPromo",
                    tool_type="backend_api",
                    description="Generate 15% referral promo code (unlimited uses, no expiry)",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/CreateOwnershipMapping",
                    tool_type="backend_api",
                    description="Create atomic promo + ownership mapping",
                    requires_approval=False,
                ),
            ],
        },
        "review_promo": {
            "flow_type": FlowType.REVIEW_PROMO,
            "mode": ProcessingMode.MODE_A_DETERMINISTIC,
            "requires_approval": False,
            "tools": [
                ToolCall(
                    tool_name="fuckhr-api/CheckReviewEligibility",
                    tool_type="backend_api",
                    description="Check if user has eligible review and no existing promo",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/GenerateReviewPromo",
                    tool_type="backend_api",
                    description="Generate 15% review promo (user-bound, max_uses=1)",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/SendReviewForm",
                    tool_type="backend_api",
                    description="Send review form if no eligible review found",
                    requires_approval=False,
                ),
            ],
        },
        "crypto_alt_payment": {
            "flow_type": FlowType.CRYPTO_ALT_PAYMENT,
            "mode": ProcessingMode.MODE_A_DETERMINISTIC,
            "requires_approval": True,
            "tools": [
                ToolCall(
                    tool_name="secret-service/GetRequisites",
                    tool_type="backend_api",
                    description="Get crypto/foreign card payment requisites (from secret service only)",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/GenerateQuote",
                    tool_type="backend_api",
                    description="Generate payment quote (rate, fee, TTL)",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/VerifyPaymentProof",
                    tool_type="backend_api",
                    description="Verify payment proof (tx hash for crypto, receipt for cards)",
                    requires_approval=False,
                ),
                ToolCall(
                    tool_name="fuckhr-api/GrantSubscription",
                    tool_type="backend_api",
                    description="Grant subscription (manual, no auto-renewal)",
                    requires_approval=True,
                ),
            ],
        },
    }

    def __init__(self, fallback_matcher: Optional[FlowMatcher] = None):
        """Initialize intent router.

        Args:
            fallback_matcher: Optional FlowMatcher for fallback pattern matching.
        """
        self.flow_matcher = fallback_matcher or FlowMatcher()

    def route(self, question: str) -> ProcessingContext:
        """Route a question to MODE_A or MODE_B.

        Args:
            question: User question.

        Returns:
            ProcessingContext with determined mode and flow information.
        """
        context = ProcessingContext(question=question)

        # Try to match with deterministic flows
        flow_match = self.flow_matcher.match(question)

        if flow_match and flow_match.flow_name in self.FLOW_DEFINITIONS:
            # MODE_A: Deterministic flow matched
            flow_def = self.FLOW_DEFINITIONS[flow_match.flow_name]

            context.processing_mode = flow_def["mode"]
            context.flow_type = flow_def["flow_type"]
            context.confidence = flow_match.match_score
            context.requires_staff_approval = flow_def["requires_approval"]

            # Add expected tools
            for tool in flow_def["tools"]:
                context.add_expected_tool(tool)

            logger.info(
                f"[INTENT ROUTER] MODE_A matched: {flow_match.flow_name} "
                f"(confidence: {flow_match.match_score}, approval: {flow_def['requires_approval']})"
            )

            if flow_match.needs_staff_approval:
                context.requires_staff_approval = True
                context.handoff_triggered = True
                context.handoff_reason = (
                    f"Escalation detected: {flow_match.escalation_type}"
                )

        else:
            # MODE_B: No deterministic flow, will use RAG + LLM
            context.processing_mode = ProcessingMode.MODE_B_INVESTIGATION
            context.confidence = 0.0

            logger.info(
                "[INTENT ROUTER] No MODE_A match, proceeding to MODE_B (RAG + LLM investigation)"
            )

        return context
