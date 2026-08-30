"""Processing phases and operation logging for clear bot behavior visualization."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ProcessingMode(Enum):
    """Explicit processing mode of the bot."""

    MODE_A_DETERMINISTIC = "mode_a_deterministic"
    """Deterministic State Machine (6 flows: refund, career, jobs, referral, review, crypto)."""

    MODE_B_INVESTIGATION = "mode_b_investigation"
    """LLM Investigation with RAG for non-deterministic questions."""


class OperationPhase(Enum):
    """Explicit phase of bot operation."""

    INTENT_CLASSIFICATION = "intent_classification"
    """Classify question: is it MODE_A or MODE_B?"""

    STATE_MACHINE_INIT = "state_machine_initialization"
    """Initialize State Machine for MODE_A flows."""

    TOOL_EXECUTION = "tool_execution"
    """Execute backend tools (API calls)."""

    RAG_RETRIEVAL = "rag_retrieval"
    """RAG search in knowledge base (MODE_B)."""

    LLM_GENERATION = "llm_generation"
    """LLM answer generation or improvement (read-only)."""

    HANDOFF = "handoff"
    """Escalate to human support."""


class FlowType(Enum):
    """Six deterministic flows from Technical Spec (стр. 9-10 ТЗ)."""

    REFUND = "refund"
    """Flow 1: Refund and subscription deletion (staff approval required)."""

    CAREER_HELP = "career_help"
    """Flow 2: Career assistance and expert consultations."""

    JOB_ARCHIVAL = "job_archival"
    """Flow 3: Job vacancy persistent suppression (staff approval required)."""

    REFERRAL_PROMO = "referral_promo"
    """Flow 4: Referral promo code generation."""

    REVIEW_PROMO = "review_promo"
    """Flow 5: Review promo code generation."""

    CRYPTO_ALT_PAYMENT = "crypto_alt_payment"
    """Flow 6: Crypto/foreign card payment (staff approval required)."""


@dataclass
class ToolCall:
    """Represents a backend tool call (API, script execution)."""

    tool_name: str
    """Tool identifier: 'fuckhr-api/GetUserPayments', 'jobs-api/Suppress', etc."""

    tool_type: str
    """Type: 'backend_api', 'script', 'script_execution'."""

    description: str
    """Human-readable description of what this tool does."""

    requires_approval: bool = False
    """Whether this tool requires staff approval."""

    status: Optional[str] = None
    """Execution status: 'pending', 'success', 'failed'."""

    result: Optional[dict[str, Any]] = None
    """Tool execution result."""

    error: Optional[str] = None
    """Error message if tool failed."""


@dataclass
class PhaseLog:
    """Log entry for a single operation phase."""

    phase: OperationPhase
    """Which phase this log describes."""

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    """When this phase started."""

    status: str = "pending"
    """Phase status: 'pending', 'running', 'success', 'failed'."""

    details: dict[str, Any] = field(default_factory=dict)
    """Phase-specific details."""

    error: Optional[str] = None
    """Error message if phase failed."""


@dataclass
class ProcessingContext:
    """Context for the entire question processing."""

    question: str
    """Original user question."""

    processing_mode: Optional[ProcessingMode] = None
    """Determined mode: MODE_A or MODE_B."""

    flow_type: Optional[FlowType] = None
    """If MODE_A: which of 6 flows."""

    confidence: float = 0.0
    """Confidence in the classification/answer (0.0-1.0)."""

    phases: list[PhaseLog] = field(default_factory=list)
    """Log of all processing phases."""

    expected_tools: list[ToolCall] = field(default_factory=list)
    """For MODE_A: expected backend tools to be called."""

    executed_tools: list[ToolCall] = field(default_factory=list)
    """Tools that were actually executed."""

    final_answer: Optional[str] = None
    """Final answer or response to user."""

    requires_staff_approval: bool = False
    """Whether this action requires staff review."""

    approval_token: Optional[str] = None
    """Approval token for staff action (if required)."""

    handoff_triggered: bool = False
    """Whether bot handed off to human support."""

    handoff_reason: Optional[str] = None
    """Reason for handoff (if triggered)."""

    def add_phase_log(
        self,
        phase: OperationPhase,
        status: str = "pending",
        details: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Add a phase log entry."""
        self.phases.append(
            PhaseLog(
                phase=phase,
                status=status,
                details=details or {},
                error=error,
            )
        )

    def add_expected_tool(self, tool: ToolCall) -> None:
        """Add an expected tool for MODE_A flows."""
        self.expected_tools.append(tool)

    def add_executed_tool(self, tool: ToolCall) -> None:
        """Add an executed tool."""
        self.executed_tools.append(tool)

    def format_for_display(self) -> str:
        """Format context for user display."""
        lines = []

        # Processing mode and flow type
        if self.processing_mode:
            lines.append(f"Processing Mode: {self.processing_mode.value.upper()}")
        if self.flow_type:
            lines.append(f"Flow Type: {self.flow_type.value.upper()}")
        if self.confidence:
            lines.append(f"Confidence: {self.confidence:.2f}")

        # Expected tools for MODE_A
        if self.expected_tools:
            lines.append("\nExpected Operations:")
            for i, tool in enumerate(self.expected_tools, 1):
                approval_str = " (requires approval)" if tool.requires_approval else ""
                lines.append(f"  {i}. {tool.description}{approval_str}")

        # Phase logs
        if self.phases:
            lines.append("\nProcessing Phases:")
            for log in self.phases:
                status_icon = (
                    "✓"
                    if log.status == "success"
                    else "✗" if log.status == "failed" else "→"
                )
                lines.append(f"  {status_icon} {log.phase.value}")
                if log.details:
                    for key, val in log.details.items():
                        lines.append(f"      {key}: {val}")
                if log.error:
                    lines.append(f"      ERROR: {log.error}")

        # Executed tools
        if self.executed_tools:
            lines.append("\nExecuted Tools:")
            for i, tool in enumerate(self.executed_tools, 1):
                status_icon = (
                    "✓"
                    if tool.status == "success"
                    else "✗" if tool.status == "failed" else "→"
                )
                lines.append(f"  {status_icon} {tool.tool_name}")
                if tool.status == "failed" and tool.error:
                    lines.append(f"      ERROR: {tool.error}")

        # Approval info
        if self.requires_staff_approval:
            lines.append("\nStaff Approval Required: YES")
            if self.approval_token:
                lines.append(f"Approval Token: {self.approval_token[:32]}...")

        # Handoff info
        if self.handoff_triggered:
            lines.append("\nHandoff Triggered: YES")
            if self.handoff_reason:
                lines.append(f"Reason: {self.handoff_reason}")

        return "\n".join(lines)
