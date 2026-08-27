# QuickOffer Support Bot - Architecture Guide

## Overview

The bot operates in **two distinct modes** with clear separation of concerns:

- **MODE A**: Deterministic State Machine (6 predefined flows)
- **MODE B**: LLM Investigation with RAG (all other questions)

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER QUESTION                            │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────────┐
                    │  PHASE 1: INTENT   │
                    │ CLASSIFICATION     │
                    └────────┬───────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
        ┌───────────────┐         ┌──────────────┐
        │   MODE A      │         │   MODE B     │
        │   Deterministic│         │ Investigation│
        │   State Machine│         │  & Handoff   │
        └───────┬───────┘         └──────┬───────┘
                │                         │
    ┌───────────┴────────────┐            │
    │ PHASE 2: STATE MACHINE │            │
    │   INITIALIZATION       │            ▼
    │                        │    ┌──────────────────┐
    │ 6 Flows (TZ стр. 9):   │    │ PHASE 2: RAG     │
    │ 1. Refund (staff app)  │    │ RETRIEVAL        │
    │ 2. Career Help         │    │ (Hybrid Search)  │
    │ 3. Job Archive (app)   │    └──────┬───────────┘
    │ 4. Referral Promo      │           │
    │ 5. Review Promo        │           ▼
    │ 6. Crypto/Alt (app)    │    ┌──────────────────┐
    │                        │    │ PHASE 3: LLM     │
    │ = Серверные state      │    │ GENERATION       │
    │   machines с пред.     │    │ (Read-Only)      │
    │   определённым ходом   │    └──────┬───────────┘
    └────────────┬───────────┘           │
                 │                       │
                 ▼                       │
        ┌────────────────┐               │
        │ PHASE 3: TOOL  │               │
        │ EXECUTION      │               │
        │ (Backend API)  │               │
        └────────┬───────┘               │
                 │                       │
                 └───────────┬───────────┘
                             │
                             ▼
                    ┌────────────────────┐
                    │ PHASE 4: RESPONSE  │
                    │ (Answer or Handoff)│
                    └────────────────────┘
```

---

## Phase Definitions

### PHASE 1: INTENT CLASSIFICATION

**Purpose**: Determine if question belongs to MODE_A or MODE_B.

**Input**: User question (string)

**Process**:
1. Match question against predefined instruction flows
2. Extract keywords and patterns
3. Calculate confidence score
4. Determine processing mode

**Output**: `ProcessingContext` with:
- `processing_mode`: MODE_A_DETERMINISTIC or MODE_B_INVESTIGATION
- `flow_type`: One of 6 flows (if MODE_A)
- `confidence`: Match score (0.0-1.0)
- `expected_tools`: List of backend tools to be called

**Example Output (MODE_A)**:
```
Processing Mode: MODE_A_DETERMINISTIC
Flow Type: REFUND
Confidence: 0.95
Expected Operations:
  1. Retrieve user payment history
  2. Get refund eligibility and preview
  3. Validate refund basis
  4. Process refund in payment provider (requires approval)
  5. Soft-delete subscription (requires approval)
```

**Example Output (MODE_B)**:
```
Processing Mode: MODE_B_INVESTIGATION
Flow Type: None
Confidence: 0.0
(Will proceed to RAG + LLM)
```

---

### PHASE 2: Flow-Specific Processing

#### MODE_A: State Machine Initialization

**Purpose**: Prepare state machine for deterministic flow execution.

**Input**: `ProcessingContext` from PHASE 1

**State Machine Structure**:
```
INITIAL
  ├─ GATHERING_INFO
  │  ├─ ANALYZING
  │  │  ├─ PROPOSING_SOLUTION
  │  │  │  ├─ WAITING_APPROVAL (if approval required)
  │  │  │  │  ├─ EXECUTING_ACTION
  │  │  │  │  │  ├─ RESOLVED
  │  │  │  │  │  ├─ ESCALATED
  │  │  │  │  │
  │  │  │  ├─ ESCALATED
  │  │  │
  │  │  ├─ ESCALATED
  │  │
  │  ├─ ESCALATED
  │
  ├─ ESCALATED
```

**Expected Tools**: Populated in PHASE 1, specific to each flow:

1. **REFUND** (requires staff approval):
   - fuckhr-api/GetUserPayments
   - fuckhr-api/GetRefundPreview
   - fuckhr-api/ValidateRefundBasis
   - YooKassa/ProcessRefund (staff action)
   - fuckhr-api/RevokeSubscription

2. **CAREER_HELP**:
   - fuckhr-api/CheckEligibility
   - fuckhr-api/CreateCareerTicket
   - internal-telegram/SendToCareerChat

3. **JOB_ARCHIVAL** (requires staff approval):
   - jobs-api/LookupJob
   - jobs-api/PersistentSuppress (staff action)
   - jobs-api/VerifySuppressionStatus

4. **REFERRAL_PROMO**:
   - fuckhr-api/CheckReferralOwnership
   - fuckhr-api/GenerateReferralPromo
   - fuckhr-api/CreateOwnershipMapping

5. **REVIEW_PROMO**:
   - fuckhr-api/CheckReviewEligibility
   - fuckhr-api/GenerateReviewPromo
   - fuckhr-api/SendReviewForm

6. **CRYPTO_ALT_PAYMENT** (requires staff approval):
   - secret-service/GetRequisites
   - fuckhr-api/GenerateQuote
   - fuckhr-api/VerifyPaymentProof
   - fuckhr-api/GrantSubscription (staff action)

#### MODE_B: RAG Retrieval

**Purpose**: Search knowledge base for relevant answers.

**Input**: User question

**Process**:
1. **BM25 Search**: Keyword-based retrieval
2. **Semantic Search**: Vector similarity search
3. **Reranking**: Score and rank combined results
4. **Confidence Calculation**: Determine answer quality

**Scoring**:
```
Final Score = (BM25_score × 0.3) + (Semantic_score × 0.5) + (Rerank_bonus × 0.2)
```

**Output**: Top matching Q&A with scores:
- `bm25_score`: Keyword matching score
- `semantic_score`: Vector similarity score
- `rerank_score`: Final reranked score
- `confidence`: Overall answer confidence

---

### PHASE 3: Tool Execution or LLM Generation

#### MODE_A: Tool Execution

**Purpose**: Execute backend tools in sequence based on state machine.

**Input**: State machine context

**Process**:
1. For each state transition:
   - Call corresponding backend API
   - Validate response
   - Update context
   - Transition to next state
2. Collect approval tokens if required
3. Prepare for staff approval phase

**Tools**:
- Read-only tools: GetUserPayments, CheckEligibility, LookupJob
- Mutation tools (approval required): ProcessRefund, RevokeSubscription, PersistentSuppress
- Creation tools: GeneratePromo, CreateTicket, GrantSubscription

#### MODE_B: LLM Generation

**Purpose**: Generate answer using LLM (read-only operations only).

**Input**: Question + RAG context (if found)

**Process**:
1. If RAG confidence < 0.65:
   - Use LLM to improve answer
   - Add RAG context to prompt
2. If no RAG match:
   - Use LLM fallback generation
   - Warn user about low confidence
3. Validate answer against security policy

**LLM Tools Available**:
- ✅ Approved FAQ/Knowledge base
- ✅ User support history (read-only)
- ✅ Subscription status (read-only)
- ✅ Masked payment history
- ✅ Current incidents
- ❌ No write/mutation tools
- ❌ No raw SQL
- ❌ No arbitrary HTTP

---

### PHASE 4: Handoff or Response

**Purpose**: Deliver answer or escalate to human support.

**Input**: Processing context with results

**Handoff Triggers** (from ТЗ стр. 269-280):
1. User explicitly requests human ("оператор", "менеджер")
2. Identity not verified (auth failure)
3. Money/legal issues (refund, chargeback, lawsuit)
4. Account security concern (hacked, breach)
5. Data request (GDPR, deletion, export)
6. Tool failure cascade (2+ consecutive failures)
7. Double LLM failure (2+ consecutive generation failures)

**Output**:
- MODE_A with approval required: Show approval token, wait for staff
- MODE_A without approval: Show answer
- MODE_B with high confidence: Show answer
- MODE_B with low confidence: Ask clarification or handoff
- Any handoff trigger: Escalate to human support team

---

## Code Components

### `processing_phases.py`

Defines data structures for explicit phase tracking:

```python
class ProcessingMode(Enum):
    MODE_A_DETERMINISTIC = "mode_a_deterministic"
    MODE_B_INVESTIGATION = "mode_b_investigation"

class OperationPhase(Enum):
    INTENT_CLASSIFICATION = "intent_classification"
    STATE_MACHINE_INIT = "state_machine_initialization"
    TOOL_EXECUTION = "tool_execution"
    RAG_RETRIEVAL = "rag_retrieval"
    LLM_GENERATION = "llm_generation"
    HANDOFF = "handoff"

class FlowType(Enum):
    REFUND = "refund"
    CAREER_HELP = "career_help"
    JOB_ARCHIVAL = "job_archival"
    REFERRAL_PROMO = "referral_promo"
    REVIEW_PROMO = "review_promo"
    CRYPTO_ALT_PAYMENT = "crypto_alt_payment"

@dataclass
class ProcessingContext:
    question: str
    processing_mode: Optional[ProcessingMode]
    flow_type: Optional[FlowType]
    confidence: float
    phases: list[PhaseLog]
    expected_tools: list[ToolCall]
    executed_tools: list[ToolCall]
    final_answer: Optional[str]
    requires_staff_approval: bool
    handoff_triggered: bool
```

### `intent_router.py`

Routes questions to MODE_A or MODE_B with full tool definitions:

```python
class IntentRouter:
    FLOW_DEFINITIONS = {
        "return_refund": {
            "flow_type": FlowType.REFUND,
            "mode": ProcessingMode.MODE_A_DETERMINISTIC,
            "requires_approval": True,
            "tools": [...]  # List of ToolCall objects
        },
        # ... other 5 flows
    }
    
    def route(self, question: str) -> ProcessingContext:
        # Return context with determined mode, flow, and tools
```

### `interactive_demo.py`

Interactive CLI with clear phase logging:

```python
class InteractiveDemo:
    def process_question(self, question: str) -> dict:
        # PHASE 1: Intent Classification
        context = self.intent_router.route(question)
        
        # PHASE 2: MODE-specific processing
        if MODE_A:
            # Initialize state machine
            # Show expected tools
        else:
            # RAG retrieval
            # LLM generation if needed
        
        # PHASE 3: Tool execution (MODE_A) or LLM (MODE_B)
        # PHASE 4: Response or handoff
        
        return result
```

---

## Key Terminology

| Term | Definition | Example |
|------|-----------|---------|
| **Flow** | Deterministic state machine from ТЗ (6 types) | "refund", "career_help" |
| **Mode** | Processing approach (A=deterministic, B=investigation) | MODE_A_DETERMINISTIC |
| **Phase** | Sequential processing step | INTENT_CLASSIFICATION |
| **Tool** | Backend API or service call | "fuckhr-api/GetUserPayments" |
| **Instruction** | Pre-defined answer pattern (now called InstructionMatch) | "return_refund" instruction |
| **FlowMatch** | Result of pattern matching (deprecated naming, use InstructionMatch) | Confidence 0.95 for "refund" |

---

## Logging & Debugging

### Interactive Demo Output Example

**MODE_A Flow**:
```
================================================================================
[PHASE 1] INTENT CLASSIFICATION
================================================================================

Processing Mode: MODE_A_DETERMINISTIC
Flow Type: REFUND
Confidence: 0.95

Expected Operations:
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
```

**MODE_B Flow**:
```
================================================================================
[PHASE 1] INTENT CLASSIFICATION
================================================================================

Processing Mode: MODE_B_INVESTIGATION
Confidence: 0.0

================================================================================
[PHASE 2] RAG RETRIEVAL
================================================================================

Searching in RAG dataset (Hybrid Search)...

✓ Found relevant Q&A
  BM25 Score: 0.72
  Semantic Score: 0.81
  Rerank Score: 0.75
  Similar question: How do I reset my password?...

================================================================================
[PHASE 3] LLM IMPROVEMENT
================================================================================

Confidence too low (0.72)
Attempting LLM improvement...

✓ LLM improved answer
  Confidence: 0.72 → 0.85
```

---

## Integration with Real Flows

The `InteractiveDemo` currently shows **simulated** tool execution for MODE_A flows.

To integrate with real `src/services/flows/` logic:

1. Import actual flow engines (RefundFlowEngine, etc.)
2. Replace simulation with real state transitions
3. Call actual backend APIs instead of mock execution
4. Handle real approval workflows

Example:
```python
# Instead of:
tool.status = "success"

# Do:
refund_engine = RefundFlowEngine(approval_service, fuckhr_client)
payments = await refund_engine.get_user_payments(user_id)
context.executed_tools[0].result = payments
```

---

## Security Model

### LLM Read-Only Isolation
- ✅ LLM can only read approved FAQ, history, and public data
- ❌ LLM cannot execute mutations or access raw credentials
- ❌ LLM cannot choose user ID, amount, or discount
- ✅ All mutations go through typed HTTP clients with approval

### Approval Flow
1. User initiates high-risk action (refund, archive, crypto grant)
2. Bot collects data and creates frozen action snapshot
3. Action hash validates parameter integrity
4. Staff approves via Telegram with approval token
5. Token tied to specific action_id and params
6. Changing params invalidates approval
7. Only approved staff roles can execute

### Handoff Policy
- Bot escalates automatically when:
  - User requests human support
  - Identity verification fails
  - High-risk operations (money, legal)
  - Account security concerns
  - Repeated tool failures
  - Unknown policy

---

## Testing & Validation

### Run Interactive Demo
```bash
python -m src.benchmarking.interactive_demo
```

Examples to test:
- MODE_A: "как мне вернуть деньги?" → Refund flow
- MODE_A: "помогите с карьерой" → Career help flow
- MODE_A: "промокод для друга" → Referral promo flow
- MODE_B: "как перезагрузить приложение?" → RAG + LLM

### Run Benchmark
```bash
python -m src.benchmarking.benchmark
```

Outputs:
- Flow matching accuracy
- RAG retrieval quality
- LLM improvement effectiveness
- Mode distribution (A vs B)

---

## References

- ТЗ: Technical Specification (Техническое задание.pdf)
  - Flows: стр. 9-10 (Mode A definition)
  - State machines: стр. 132-244 (Flow details)
  - LLM isolation: стр. 25, 255-280 (Security & handoff)
- `README.md`: High-level architecture
- `src/services/fsm.py`: SupportFlowFSM implementation
- `src/services/flows/`: Flow engines (refund, career, etc.)
