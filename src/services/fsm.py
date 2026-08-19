"""Finite State Machine service for deterministic support flows."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SupportFlowState(str, Enum):
    """Support flow state enumeration."""

    INITIAL = "initial"
    GATHERING_INFO = "gathering_info"
    ANALYZING = "analyzing"
    PROPOSING_SOLUTION = "proposing_solution"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING_ACTION = "executing_action"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class FSMTransition(BaseModel):
    """FSM transition model."""

    from_state: SupportFlowState
    to_state: SupportFlowState
    condition: str | None = None
    action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FSMContext(BaseModel):
    """FSM context with validation."""

    current_state: SupportFlowState = SupportFlowState.INITIAL
    ticket_id: str
    flow_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    history: list[SupportFlowState] = Field(default_factory=list)


class SupportFlowFSM:
    """Deterministic FSM for support ticket flows."""

    def __init__(self) -> None:
        """Initialize FSM with transition rules."""
        self.transitions: dict[
            SupportFlowState, list[SupportFlowState]
        ] = {
            SupportFlowState.INITIAL: [
                SupportFlowState.GATHERING_INFO,
                SupportFlowState.ESCALATED,
            ],
            SupportFlowState.GATHERING_INFO: [
                SupportFlowState.ANALYZING,
                SupportFlowState.ESCALATED,
            ],
            SupportFlowState.ANALYZING: [
                SupportFlowState.PROPOSING_SOLUTION,
                SupportFlowState.ESCALATED,
            ],
            SupportFlowState.PROPOSING_SOLUTION: [
                SupportFlowState.WAITING_APPROVAL,
                SupportFlowState.ESCALATED,
            ],
            SupportFlowState.WAITING_APPROVAL: [
                SupportFlowState.EXECUTING_ACTION,
                SupportFlowState.ESCALATED,
            ],
            SupportFlowState.EXECUTING_ACTION: [
                SupportFlowState.RESOLVED,
                SupportFlowState.ESCALATED,
            ],
            SupportFlowState.RESOLVED: [],
            SupportFlowState.ESCALATED: [],
        }

    def can_transition(
        self, from_state: SupportFlowState, to_state: SupportFlowState
    ) -> bool:
        """Check if transition is allowed.

        Args:
            from_state: Current state.
            to_state: Target state.

        Returns:
            bool: True if transition is allowed.
        """
        return to_state in self.transitions.get(from_state, [])

    def transition(
        self,
        context: FSMContext,
        to_state: SupportFlowState,
        metadata: dict[str, Any] | None = None,
    ) -> FSMContext:
        """Perform state transition with validation.

        Args:
            context: Current FSM context.
            to_state: Target state.
            metadata: Optional transition metadata.

        Returns:
            FSMContext: Updated context.

        Raises:
            ValueError: If transition is not allowed.
        """
        if not self.can_transition(context.current_state, to_state):
            raise ValueError(
                f"Invalid transition: {context.current_state} -> {to_state}"
            )

        context.history.append(context.current_state)
        context.current_state = to_state

        if metadata:
            context.data.update(metadata)

        return context

    def get_allowed_transitions(
        self, current_state: SupportFlowState
    ) -> list[SupportFlowState]:
        """Get allowed transitions from current state.

        Args:
            current_state: Current state.

        Returns:
            list: Allowed next states.
        """
        return self.transitions.get(current_state, [])
