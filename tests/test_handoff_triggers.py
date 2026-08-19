"""Integration tests for Human Handoff triggers."""

import pytest
import uuid
from datetime import datetime

from src.services.handoff_engine import (
    HandoffDetector,
    HandoffService,
    HandoffTriggerType,
)


class TestHandoffDetector:
    """Test suite for HandoffDetector."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.detector = HandoffDetector()

    def test_trigger_1_explicit_request_english(self) -> None:
        """Test explicit human request trigger (English)."""
        message = "I need to talk to a human operator"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.EXPLICIT_REQUEST
        assert "explicit" in reason.lower()

    def test_trigger_1_explicit_request_russian(self) -> None:
        """Test explicit human request trigger (Russian)."""
        message = "Подключите меня к человеку, пожалуйста"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.EXPLICIT_REQUEST

    def test_trigger_2_identity_not_verified(self) -> None:
        """Test identity not verified trigger."""
        message = "What is my account balance?"
        context = {"identity_verified": False}
        should_handoff, trigger_type, reason = self.detector.detect(
            message, context
        )

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.IDENTITY_NOT_VERIFIED

    def test_trigger_3_money_issue_refund(self) -> None:
        """Test money/legal issue trigger - refund keyword."""
        message = "I want a refund for my last purchase"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.MONEY_LEGAL_ISSUE

    def test_trigger_3_money_issue_chargeback(self) -> None:
        """Test money/legal issue trigger - chargeback keyword."""
        message = "I'm disputing this charge via chargeback"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.MONEY_LEGAL_ISSUE

    def test_trigger_3_money_issue_legal(self) -> None:
        """Test money/legal issue trigger - legal keyword."""
        message = "This is a lawsuit matter"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.MONEY_LEGAL_ISSUE

    def test_trigger_4_account_security_hacked(self) -> None:
        """Test account security trigger - hacked keyword."""
        message = "My account has been hacked!"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.ACCOUNT_SECURITY

    def test_trigger_4_account_security_takeover(self) -> None:
        """Test account security trigger - takeover keyword."""
        message = "I suspect account takeover"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.ACCOUNT_SECURITY

    def test_trigger_5_data_request_export(self) -> None:
        """Test data request trigger - export keyword."""
        message = "Can you export all my data?"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.DATA_REQUEST_UNKNOWN_POLICY

    def test_trigger_5_data_request_gdpr(self) -> None:
        """Test data request trigger - GDPR keyword."""
        message = "I want to exercise my GDPR rights"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.DATA_REQUEST_UNKNOWN_POLICY

    def test_trigger_6_tool_failure_cascade(self) -> None:
        """Test tool failure cascade trigger."""
        message = "What's my balance?"
        context = {"tool_failure_count": 2}
        should_handoff, trigger_type, reason = self.detector.detect(
            message, context
        )

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.TOOL_FAILURE_CASCADE

    def test_trigger_6_tool_failure_single(self) -> None:
        """Test that single tool failure does NOT trigger handoff."""
        message = "What's my balance?"
        context = {"tool_failure_count": 1}
        should_handoff, trigger_type, reason = self.detector.detect(
            message, context
        )

        assert should_handoff is False

    def test_trigger_7_double_llm_failure(self) -> None:
        """Test double LLM failure trigger."""
        message = "Tell me something"
        context = {"llm_failure_count": 2}
        should_handoff, trigger_type, reason = self.detector.detect(
            message, context
        )

        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.DOUBLE_LLM_FAILURE

    def test_trigger_7_single_llm_failure(self) -> None:
        """Test that single LLM failure does NOT trigger handoff."""
        message = "Tell me something"
        context = {"llm_failure_count": 1}
        should_handoff, trigger_type, reason = self.detector.detect(
            message, context
        )

        assert should_handoff is False

    def test_no_trigger_normal_question(self) -> None:
        """Test normal question without triggers."""
        message = "What are the business hours?"
        should_handoff, trigger_type, reason = self.detector.detect(message)

        assert should_handoff is False
        assert trigger_type is None

    def test_record_tool_failure(self) -> None:
        """Test recording tool failures."""
        conversation_id = "conv-123"

        # Record first failure
        self.detector.record_tool_failure(conversation_id)
        assert self.detector.tool_failure_counter.get(
            f"tool_{conversation_id}", 0
        ) == 1

        # Record second failure
        self.detector.record_tool_failure(conversation_id)
        assert self.detector.tool_failure_counter.get(
            f"tool_{conversation_id}", 0
        ) == 2

    def test_record_llm_failure(self) -> None:
        """Test recording LLM failures."""
        conversation_id = "conv-456"

        # Record first failure
        self.detector.record_llm_failure(conversation_id)
        assert self.detector.llm_failure_counter.get(
            f"llm_{conversation_id}", 0
        ) == 1

        # Record second failure
        self.detector.record_llm_failure(conversation_id)
        assert self.detector.llm_failure_counter.get(
            f"llm_{conversation_id}", 0
        ) == 2

    def test_reset_failures(self) -> None:
        """Test resetting failure counters."""
        conversation_id = "conv-789"

        # Record failures
        self.detector.record_tool_failure(conversation_id)
        self.detector.record_llm_failure(conversation_id)

        # Verify they were recorded
        assert self.detector.tool_failure_counter.get(
            f"tool_{conversation_id}", 0
        ) > 0
        assert self.detector.llm_failure_counter.get(
            f"llm_{conversation_id}", 0
        ) > 0

        # Reset
        self.detector.reset_failures(conversation_id)

        # Verify they were cleared
        assert f"tool_{conversation_id}" not in self.detector.tool_failure_counter
        assert f"llm_{conversation_id}" not in self.detector.llm_failure_counter


class TestHandoffService:
    """Test suite for HandoffService."""

    @pytest.mark.asyncio
    async def test_check_and_execute_no_handoff(self) -> None:
        """Test check_and_execute with no handoff needed."""
        service = HandoffService()

        result = await service.check_and_execute(
            "What are your business hours?",
            uuid.uuid4(),
            "user-123",
        )

        assert result["handoff_triggered"] is False
        assert result["ticket_id"] is None

    @pytest.mark.asyncio
    async def test_check_and_execute_explicit_request(self) -> None:
        """Test check_and_execute with explicit handoff request."""
        service = HandoffService()

        result = await service.check_and_execute(
            "I need to talk to an operator",
            uuid.uuid4(),
            "user-456",
        )

        assert result["handoff_triggered"] is True
        assert result["ticket_id"] is not None
        assert result["trigger_type"] == "explicit_request"

    @pytest.mark.asyncio
    async def test_check_and_execute_money_issue(self) -> None:
        """Test check_and_execute with money issue trigger."""
        service = HandoffService()

        result = await service.check_and_execute(
            "I want a refund",
            uuid.uuid4(),
            "user-789",
        )

        assert result["handoff_triggered"] is True
        assert result["ticket_id"] is not None
        assert result["trigger_type"] == "money_legal_issue"

    @pytest.mark.asyncio
    async def test_check_and_execute_identity_not_verified(self) -> None:
        """Test check_and_execute with identity not verified."""
        service = HandoffService()

        result = await service.check_and_execute(
            "What's my account status?",
            uuid.uuid4(),
            "user-101",
            context={"identity_verified": False},
        )

        assert result["handoff_triggered"] is True
        assert result["ticket_id"] is not None
        assert result["trigger_type"] == "identity_not_verified"

    def test_record_tool_failure(self) -> None:
        """Test recording tool failure in service."""
        service = HandoffService()
        conversation_id = "conv-111"

        service.record_tool_failure(conversation_id)

        # Verify via detector
        assert service.detector.tool_failure_counter.get(
            f"tool_{conversation_id}", 0
        ) == 1

    def test_record_llm_failure(self) -> None:
        """Test recording LLM failure in service."""
        service = HandoffService()
        conversation_id = "conv-222"

        service.record_llm_failure(conversation_id)

        # Verify via detector
        assert service.detector.llm_failure_counter.get(
            f"llm_{conversation_id}", 0
        ) == 1

    def test_reset_failures(self) -> None:
        """Test resetting failures in service."""
        service = HandoffService()
        conversation_id = "conv-333"

        # Record failures
        service.record_tool_failure(conversation_id)
        service.record_llm_failure(conversation_id)

        # Reset
        service.reset_failures(conversation_id)

        # Verify both are cleared
        assert f"tool_{conversation_id}" not in service.detector.tool_failure_counter
        assert f"llm_{conversation_id}" not in service.detector.llm_failure_counter


class TestHandoffTriggerPriority:
    """Test trigger priority and ordering."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.detector = HandoffDetector()

    def test_explicit_request_takes_priority(self) -> None:
        """Test that explicit request is checked first."""
        # Message has both explicit request and money keyword
        message = "I need a human and I want a refund"

        should_handoff, trigger_type, reason = self.detector.detect(message)

        # Should trigger on explicit request (first in detection order)
        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.EXPLICIT_REQUEST

    def test_identity_takes_priority_over_others(self) -> None:
        """Test that identity check happens early."""
        message = "What are my stats?"
        context = {"identity_verified": False}

        should_handoff, trigger_type, reason = self.detector.detect(
            message, context
        )

        # Should trigger on identity (second in detection order)
        assert should_handoff is True
        assert trigger_type == HandoffTriggerType.IDENTITY_NOT_VERIFIED
