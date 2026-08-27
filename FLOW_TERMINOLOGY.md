# Flow Terminology Guide

## Problem Statement

The term "flow" (флоу) was used inconsistently across the codebase in 4 different contexts:

1. **FSM States** (deterministic state machine in `fsm.py`)
2. **Business Process Types** (in database `flow_type` field)
3. **Instruction Patterns** (from `flow_matcher.py`)
4. **Telegram FSM StateGroups** (in handlers)

This created confusion about what "flow" means in different parts of the system.

## Solution: Clear Terminology

### Core Concepts (Strict Definitions)

| Term | Definition | Used For | Example |
|------|-----------|----------|---------|
| **Flow** | Deterministic state machine from ТЗ (6 types) | Mode A processing | "refund flow", "career_help flow" |
| **Flow Type** | Category of deterministic workflow | Database field `flow_type` | "refund", "career_help", "job_archival" |
| **Processing Mode** | Bot's approach: deterministic (A) or investigation (B) | Intent classification | MODE_A_DETERMINISTIC, MODE_B_INVESTIGATION |
| **Processing Phase** | Sequential step in question handling | Logging and debugging | INTENT_CLASSIFICATION, STATE_MACHINE_INIT |
| **Tool** | Backend API or service call | Mode A execution | "fuckhr-api/GetUserPayments", "jobs-api/Suppress" |
| **Instruction** | Pre-defined answer pattern (replaces old "FlowMatch") | Mode B knowledge base | "return_refund instruction", "career_help instruction" |

## Code Changes

### Before (Confusing)

```python
# What does "flow" mean here?
class FlowMatch:
    flow_name: str  # Is this a state machine? A tool? An instruction?
    
# What type of "flow"?
support_ticket.flow_type = "refund"  # Backend flow? Intent? Pattern?

# Which "states"?
class SupportFlowStates(StatesGroup):  # Telegram FSM or deterministic state machine?
    waiting_for_issue = State()
```

### After (Clear)

```python
# This is a specific flow type from ТЗ
class FlowType(Enum):
    REFUND = "refund"
    CAREER_HELP = "career_help"
    JOB_ARCHIVAL = "job_archival"
    REFERRAL_PROMO = "referral_promo"
    REVIEW_PROMO = "review_promo"
    CRYPTO_ALT_PAYMENT = "crypto_alt_payment"

# This tracks bot's processing approach
class ProcessingMode(Enum):
    MODE_A_DETERMINISTIC = "mode_a_deterministic"  # State machine flow
    MODE_B_INVESTIGATION = "mode_b_investigation"   # RAG + LLM

# This tracks sequential steps
class OperationPhase(Enum):
    INTENT_CLASSIFICATION = "intent_classification"
    STATE_MACHINE_INIT = "state_machine_initialization"
    TOOL_EXECUTION = "tool_execution"
    RAG_RETRIEVAL = "rag_retrieval"
    LLM_GENERATION = "llm_generation"
    HANDOFF = "handoff"

# Explicit context with all information
@dataclass
class ProcessingContext:
    processing_mode: ProcessingMode  # MODE_A or MODE_B
    flow_type: Optional[FlowType]    # Which of 6 flows (if MODE_A)
    expected_tools: list[ToolCall]   # What APIs will be called
    phases: list[PhaseLog]           # What happened at each phase
```

## Interactive Demo Output Examples

### Example 1: MODE_A Flow (Refund)

```
[Enter your question]: как мне вернуть деньги?

================================================================================
[PHASE 1] INTENT CLASSIFICATION
================================================================================

Processing Mode: MODE_A_DETERMINISTIC      ← This is a MODE_A flow
Flow Type: REFUND                           ← Specifically the refund flow (from ТЗ)
Confidence: 0.95

Expected Operations:                        ← These are the tools that will execute
  1. Retrieve user payment history
  2. Get refund eligibility and preview
  3. Validate refund basis
  4. Process refund in payment provider (requires approval)
  5. Soft-delete subscription (requires approval)

⚠️  Staff Approval Required: YES

================================================================================
[PHASE 2] STATE MACHINE INITIALIZATION
================================================================================

Flow: REFUND
Initial State: IDENTIFY
Approval Required: True
Approval Token: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6...

================================================================================
[PHASE 3] TOOL EXECUTION (SIMULATED)
================================================================================

Simulating state machine progression:
  ✓ [1] Retrieve user payment history
  ✓ [2] Get refund eligibility and preview
  ✓ [3] Validate refund basis
  ✓ [4] Process refund in payment provider (requires approval)
  ✓ [5] Soft-delete subscription (requires approval)

✓ All 5 tools executed successfully

================================================================================
RESULT
================================================================================

Final Answer:
State machine for refund completed successfully. Awaiting staff approval for critical operations.

Confidence: 0.95 (very_high)
Approval Token: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6...

================================================================================
PROCESSING SUMMARY
================================================================================
Mode: mode_a_deterministic
Flow: refund
Confidence: 0.95
Phases: 4
Expected Tools: 5
Executed Tools: 5
```

### Example 2: MODE_B Flow (Knowledge Base)

```
[Enter your question]: как перезагрузить приложение?

================================================================================
[PHASE 1] INTENT CLASSIFICATION
================================================================================

Processing Mode: MODE_B_INVESTIGATION    ← This is NOT a MODE_A flow
Confidence: 0.0
(Will proceed to RAG + LLM)

================================================================================
[PHASE 2] RAG RETRIEVAL
================================================================================

Searching in RAG dataset (Hybrid Search)...

✓ Found relevant Q&A
  BM25 Score: 0.72
  Semantic Score: 0.81
  Rerank Score: 0.75
  Similar question: How do I restart the mobile app?...

================================================================================
[PHASE 3] LLM IMPROVEMENT
================================================================================

Confidence too low (0.72)
Attempting LLM improvement...

✓ LLM improved answer
  Confidence: 0.72 → 0.85

================================================================================
RESULT
================================================================================

Final Answer:
To restart the QuickOffer mobile app:

1. Close the app completely (swipe it away from recent apps)
2. Wait 5 seconds
3. Open the app again

If issues persist, try clearing the cache:
- iOS: Settings → QuickOffer → Clear Cache
- Android: Settings → Apps → QuickOffer → Storage → Clear Cache

Confidence: 0.85 (high)

================================================================================
PROCESSING SUMMARY
================================================================================
Mode: mode_b_investigation
Flow: None
Confidence: 0.85
Phases: 3
Expected Tools: 0
Executed Tools: 0
```

## Migration Guide

### In Code

**Old terminology** → **New terminology**

- `FlowMatch.flow_name` → Use in `IntentRouter.FLOW_DEFINITIONS` mapping, not directly
- `flow_type: str` in database → Now explicitly `FlowType` enum
- Generic "flow" in code → Use specific terms: `ProcessingMode`, `FlowType`, `OperationPhase`
- "flow state" → Use `OperationPhase` for bot processing, `SupportFlowState` only for FSM

### In Logging

**Old logs**:
```
[STAGE 1] Matching with instruction flows...
[YES] Flow matched: return_refund (score: 0.95)
```

**New logs**:
```
[PHASE 1] INTENT CLASSIFICATION
Processing Mode: MODE_A_DETERMINISTIC
Flow Type: REFUND
Confidence: 0.95
```

### In Documentation

- **Technical Spec references**: "6 flows" from ТЗ → Refer by name: Refund, Career Help, Job Archival, etc.
- **Code comments**: "flow execution" → "state machine execution" or "tool execution"
- **State machine documentation**: "support flow FSM" → "SupportFlowFSM" (explicit class name)

## Key Distinctions

### Flow vs Mode

```
Question: "как вернуть деньги?"

Flow Type: REFUND
└─ One of 6 predefined flows from ТЗ

Processing Mode: MODE_A_DETERMINISTIC
└─ Bot's approach: deterministic state machine vs LLM investigation
```

### Flow Type vs Phase

```
Question: "помогите с карьерой"

Flow Type: CAREER_HELP
└─ WHICH flow (determines expected tools)

Processing Phases:
  [1] INTENT_CLASSIFICATION ← BOT IDENTIFIED IT'S MODE_A
  [2] STATE_MACHINE_INIT     ← BOT PREPARED THE FLOW
  [3] TOOL_EXECUTION         ← BOT EXECUTED THE TOOLS
  [4] HANDOFF                ← BOT SENT TO STAFF
└─ WHAT THE BOT IS DOING AT EACH STEP
```

### Tool vs Flow

```
Flow: REFUND (deterministic workflow from ТЗ)
└─ Overall business process

Tools (specific operations within the flow):
  1. fuckhr-api/GetUserPayments       ← Tool 1
  2. fuckhr-api/GetRefundPreview      ← Tool 2
  3. fuckhr-api/ValidateRefundBasis   ← Tool 3
  4. YooKassa/ProcessRefund           ← Tool 4 (requires staff)
  5. fuckhr-api/RevokeSubscription    ← Tool 5 (requires staff)
└─ HOW THE FLOW IS EXECUTED
```

## Testing with Interactive Demo

```bash
python -m src.benchmarking.interactive_demo
```

Test cases to verify correct terminology:

1. **MODE_A test** (should show expected tools):
   - "как мне вернуть деньги?" → MODE_A_DETERMINISTIC, REFUND flow
   - "помогите с карьерой" → MODE_A_DETERMINISTIC, CAREER_HELP flow
   - "хочу промокод за отзыв" → MODE_A_DETERMINISTIC, REVIEW_PROMO flow

2. **MODE_B test** (should show RAG + LLM):
   - "как перезагрузить приложение?" → MODE_B_INVESTIGATION
   - "почему не работает поиск?" → MODE_B_INVESTIGATION
   - "когда откроется новая вакансия?" → MODE_B_INVESTIGATION

3. **Staff approval test**:
   - "как заархивировать вакансию?" → MODE_A_DETERMINISTIC, JOB_ARCHIVAL, requires_approval=True
   - "дайте реферальный код" → MODE_A_DETERMINISTIC, REFERRAL_PROMO, requires_approval=False

## Summary

The new architecture clarifies:

1. **Intent Classification** (PHASE 1) → Determine MODE_A vs MODE_B
2. **Flow Specification** (if MODE_A) → Which of 6 flows from ТЗ
3. **Tool Execution** (PHASE 3) → What APIs will be called
4. **Processing Phases** → Clear logging at each step

Now when you see "flow" in logs or code, you know exactly what it means:
- **"Flow"** = One of 6 deterministic workflows (Refund, Career, Job Archive, etc.)
- **"Mode"** = Bot's approach (deterministic vs investigation)
- **"Phase"** = What step the bot is currently in
- **"Tool"** = Backend API being called

This makes the bot's behavior transparent in logs and removes ambiguity.
