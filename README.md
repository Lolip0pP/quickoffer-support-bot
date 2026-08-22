# QuickOffer Support Bot Service

Telegram-based support bot service for QuickOffer with deterministic state machine flows, LLM integration, and secure M2M operations.

## Architecture

This project follows **Clean Architecture** principles with strict separation of concerns:

```
src/
├── core/              # Configuration and core utilities
├── domain/            # Business entities and interfaces
├── infrastructure/    # Database, M2M clients, external services
├── services/          # Business logic (FSM, LLM)
└── presentation/      # API endpoints and Telegram handlers
```

### Key Architectural Patterns

1. **Strict LLM Isolation**: LLM is read-only, cannot execute mutations
2. **Deterministic FSM (Mode A)**: State machines with strict Pydantic validation
3. **M2M Operations**: All state changes through typed HTTP clients with `Idempotency-Key` and `Trace-ID`
4. **Data Frozen Snapshots**: Action approvals include SHA256 hash validation
5. **Audit Logging**: Complete audit trail for all mutations

## Tech Stack

- **Language**: Python 3.12+
- **Telegram**: aiogram v3
- **Web Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy AsyncORM
- **Database Driver**: asyncpg
- **Validation**: Pydantic v2
- **Code Quality**: Black, isort, mypy

## Project Structure

```
quickoffer-support-bot/
├── src/
│   ├── core/
│   │   └── config.py              # Pydantic settings
│   ├── domain/
│   │   ├── entities.py            # Business entities
│   │   └── interfaces.py          # Abstract repositories/services
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── session.py         # SQLAlchemy setup
│   │   │   └── models.py          # ORM models
│   │   └── m2m/
│   │       └── clients.py         # M2M API clients
│   ├── services/
│   │   ├── fsm.py                 # FSM service
│   │   └── llm.py                 # LLM integration
│   └── presentation/
│       ├── telegram/
│       │   └── handlers.py        # Telegram bot handlers
│       └── api/
│           └── routes.py          # FastAPI routes
├── migrations/                     # Alembic migrations
├── alembic.ini                     # Alembic configuration
├── main.py                         # FastAPI app entry point
├── Dockerfile                      # Multi-stage Docker build
├── docker-compose.yml              # Docker Compose configuration
├── pyproject.toml                  # Project metadata and dependencies
└── .env.example                    # Environment variables template
```

## Database Models

### Conversation
Represents a Telegram conversation with a user.

```python
- id (UUID, PK)
- tg_id (int, unique, indexed)
- user_id (str, indexed)
- status (str: active|closed|suspended)
- created_at, updated_at (timestamps)
```

### SupportTicket
Support ticket within a conversation.

```python
- id (UUID, PK)
- conversation_id (FK)
- flow_type (str)
- state (str: pending|in_progress|resolved|reopened)
- metadata (JSON)
- created_at, updated_at (timestamps)
```

### SupportAction
Represents a mutation action with approval tracking.

```python
- id (UUID, PK)
- support_ticket_id (FK)
- type (str: escalate|reassign|resolve|update_metadata)
- risk_level (str: low|medium|high|critical)
- frozen_params (JSON) - Immutable action parameters
- params_hash (str) - SHA256 hash of frozen_params
- status (str: pending|approved|rejected|executed)
- idempotency_key (str, unique, indexed)
- reconciliation_status (str: pending|confirmed|failed|retrying)
- approval_actor_id (str, nullable)
- created_at, approved_at, executed_at (timestamps)
```

### AuditLog
Audit trail for all mutations.

```python
- id (UUID, PK)
- support_action_id (FK, nullable)
- actor_id (str, indexed)
- target_id (str, indexed)
- action (str: created|updated|deleted)
- payload (JSON)
- created_at (timestamp, indexed)
```

## Setup Instructions

### 1. Clone Repository

```bash
git clone <repository-url>
cd quickoffer-support-bot
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_APPROVAL_CHAT_ID=your_chat_id

# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/support_bot
DB_PASSWORD=your_secure_password

# M2M APIs
M2M_API_KEY=your_m2m_api_key
FUCKHR_API_BASE_URL=http://fuckhr-api:8001
JOBS_API_BASE_URL=http://jobs-api:8002

# LLM
LLM_PROVIDER_KEY=your_llm_key
LLM_PROVIDER=openai  # or anthropic
LLM_MODEL=gpt-4-turbo
```

### 3. Run with Docker Compose

```bash
docker-compose up -d
```

This will:
- Start PostgreSQL database
- Build and start the bot service
- Initialize the database (if using migrations)

### 4. Run Migrations

```bash
docker-compose exec bot alembic upgrade head
```

### 5. Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Set DATABASE_URL to local PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/support_bot

# Run migrations
alembic upgrade head

# Start application
uvicorn main:app --reload
```

## API Endpoints

### Health Checks

```bash
# Health check
GET /api/v1/health

# Readiness check
GET /api/v1/ready

# Metrics
GET /api/v1/metrics
```

### Webhooks

```bash
# Approval notification
POST /api/v1/webhooks/approval
{
  "action_id": "uuid",
  "status": "approved|rejected"
}

# Reconciliation update
POST /api/v1/webhooks/reconciliation
{
  "action_id": "uuid",
  "reconciliation_status": "confirmed|failed|retrying"
}
```

## Telegram Bot Commands

### Core Commands
- `/start` - Start the bot
- `/help` - Show help message
- `/issue` - Report a new issue
- `/status` - Check ticket status
- `/cancel` - Cancel current operation

### Mode A: Deterministic Flows
- `/referral_code` - Get referral promo code (15% discount, unlimited)
- `/review_promo` - Get promo code for review (15% discount, one-time use)

## Benchmarking & LLM Improvement

### LLM Improver Component (`src/benchmarking/llm_improver.py`)

Enhanced answer improvement system with intelligent RAG context tracking and refined tone control:

#### Key Features:

**1. RAG Context Tracking:**
- Explicit source type specification (FAQ, support history, documentation, RAG/historical dialog)
- RAG context/metadata about information sources
- Confidence scoring visibility in user prompts
- Quality assurance checks to verify information from knowledge base

**2. Tone & Style Control:**
- **Professional, friendly, and unhurried tone** - emphasizes customer care
- **Simple language** - avoids jargon, explains complex concepts clearly
- **User-oriented** - focuses on user needs and convenience
- **Concise yet complete** - balances brevity with informativeness
- **Mobile-friendly** - short paragraphs, clear steps, optimized for phones
- **Empathy & humanity** - acknowledges emotions, expresses willingness to help

**3. Answer Synthesis Process:**
- **Cleanup**: Removes dialog artifacts, timestamps, and casual expressions
- **Reformatting**: Converts to imperative instruction tone with numbered steps
- **Verification**: Ensures accuracy against QuickOffer policies
- **Professional formatting**: Clear structure with high readability

#### Usage:

```python
from src.benchmarking.llm_improver import LLMImprover

improver = LLMImprover()

# Basic usage (backward compatible)
improved, confidence = improver.improve_answer(
    question="How do I reset my password?",
    weak_answer="секундочку... нужно в приложение зайти...",
    confidence=0.5
)

# Advanced usage with RAG context
improved, confidence = improver.improve_answer(
    question="How do I get a refund?",
    weak_answer="Можно запросить возврат через поддержку",
    confidence=0.6,
    rag_context="Retrieved from FAQ section on refund policies",
    source_type="FAQ"
)
```

#### System Prompt Features:
- Defines role as QuickOffer support agent
- Lists 6 support categories
- Specifies tone principles with examples (good vs bad)
- Includes empathy guidelines
- Critical security rules (Telegram ID identification, no direct DB mutations)

#### User Prompt Features:
- Shows information source with confidence level
- Displays RAG context when available
- Lists synthesis tasks with clear steps
- Quality verification checklist
- Professional formatting guidelines

### Benchmark Script (`src/benchmarking/benchmark.py`)

Run performance evaluation on 10 test questions:

```bash
python -m src.benchmarking.benchmark
```

Outputs `benchmark_results.json` with:
- Flow matching accuracy
- RAG retrieval quality
- LLM improvement effectiveness
- Confidence distribution
- Processing pipeline stages

### Interactive Demo (`src/benchmarking/interactive_demo.py`)

Test the bot interactively:

```bash
python -m src.benchmarking.interactive_demo
```

Allows real-time testing of:
1. Flow matching
2. RAG retrieval
3. LLM improvement
4. Answer confidence scoring

## Code Quality

### Type Checking

```bash
mypy src/ --strict
```

### Code Formatting

```bash
black src/ --line-length 88
isort src/ --profile black
```

### Linting (if installed)

```bash
pylint src/
flake8 src/
```

## M2M Integration

The bot communicates with external APIs using typed HTTP clients:

```python
from src.infrastructure.m2m.clients import FuckHRAPIClient, JobsAPIClient

# All requests include:
# - Authorization: Bearer {api_key}
# - Idempotency-Key: {uuid} - Prevents duplicate executions
# - Trace-ID: {action_id} - Correlates requests for debugging
```

## Core Services

### 1. FSM Service (`src/services/fsm.py`)
State machine for managing deterministic conversation flows with strict state transitions.

```python
from src.services.fsm import SupportFlowFSM

fsm = SupportFlowFSM()
can_proceed = fsm.can_transition(current_state, next_state)
fsm.transition(current_state, next_state, context)
allowed = fsm.get_allowed_transitions(current_state)
```

### 2. LLM Service (`src/services/llm.py`)
**Read-only** LLM integration with support for OpenAI and Anthropic providers:

```python
from src.services.llm import get_llm_service

llm = get_llm_service()

# Read-only operations
response = await llm.generate_response(prompt)
analysis = await llm.analyze_ticket(content)
suggestion = await llm.suggest_resolution(ticket_id)
```

**Provider Configuration:**
- OpenAI: `gpt-4-turbo`, `gpt-4`, etc.
- Anthropic: `claude-3-opus`, `claude-3-sonnet`, etc.

### 3. Identity Service (`src/services/identity.py`)
Manages Telegram ↔ QuickOffer account binding:

```python
from src.services.identity import get_identity_service

identity = get_identity_service()

# Check if Telegram ID is bound
response = await identity.check_identity(telegram_id)

# Generate one-time auth link
auth_link = await identity.generate_auth_link(telegram_id, ttl_seconds=3600)

# Check and bind or generate link
result = await identity.check_and_bind_or_link(telegram_id)
```

### 4. RAG Investigation Service (`src/services/llm_investigation.py`)
Retrieval-Augmented Generation (RAG) for knowledge base queries:

```python
from src.services.llm_investigation import InvestigationService

investigation = InvestigationService()

# Investigate user query
result = await investigation.investigate(
    query="How do I reset my password?",
    user_id="user_123",
    conversation_context={"verified": True}
)

# Register Knowledge Base version
investigation.register_kb_version(
    kb_id="faq_main",
    owner="support_team",
    version="1.0.0",
    status="active",
    effective_date=datetime.now(),
    review_date=datetime(2026, 12, 31)
)
```

**KB Status Filtering:**
- ✅ Only `"active"` KBs are used
- ❌ `"draft"` and `"archived"` are excluded
- Date validation: `effective_date <= now <= review_date`

### 5. Handoff Engine (`src/services/handoff_engine.py`)
Automatic escalation to human support with 7 trigger types:

```python
from src.services.handoff_engine import get_handoff_service, HandoffTriggerType

handoff = get_handoff_service()

# Check and execute handoff if triggered
context = HandoffContext(
    conversation_id=conv_id,
    user_id="user_123",
    trigger_type=HandoffTriggerType.EXPLICIT_REQUEST,
    trigger_reason="User asked for operator"
)

is_handed_off = await handoff.check_and_execute(context)

# Track failures for cascade detection
handoff.record_tool_failure(conversation_id)
handoff.record_llm_failure(conversation_id)
handoff.reset_failures(conversation_id)
```

**7 Handoff Triggers:**
1. `EXPLICIT_REQUEST` - User asks for human ("оператора", "менеджер")
2. `IDENTITY_NOT_VERIFIED` - Auth verification failed
3. `MONEY_LEGAL_ISSUE` - Keywords: "refund", "lawsuit", "возврат"
4. `ACCOUNT_SECURITY` - Keywords: "hacked", "breach", "взломана"
5. `DATA_REQUEST_UNKNOWN_POLICY` - GDPR/data deletion requests
6. `TOOL_FAILURE_CASCADE` - 2+ consecutive tool failures
7. `DOUBLE_LLM_FAILURE` - 2+ consecutive LLM generation failures

### 6. Read-Only Tools Registry (`src/services/llm_tools.py`)
Strictly controlled set of read-only tools for LLM operations:

```python
from src.services.llm_tools import get_tools_registry

tools = get_tools_registry()

# Get available tools
available = tools.get_available_tools()

# Execute a tool
result = await tools.execute_tool("faq", query="How to reset password?")
```

**Available Tools:**
- `ApprovedFAQTool` - FAQ entries from curated KB
- `UserSupportSnapshotTool` - User support history
- `SubscriptionStatusTool` - Subscription status
- `MaskedPaymentsTool` - Masked payment history
- `SearchHealthTool` - Search service health
- `CurrentIncidentsTool` - Active incidents
- `PromoEligibilityTool` - Promo code eligibility
- `JobsPublicStatusTool` - Public job vacancy status

**Physical Isolation:**
- ❌ NO mutation tools
- ❌ NO raw SQL execution
- ❌ NO shell access
- ✅ ONLY read-only operations

### 7. Approval Service (`src/services/approval_service.py`)
Manages high-risk action approvals with frozen parameters and integrity checking:

```python
from src.services.approval_service import ApprovalService

approval_service = ApprovalService()

# Create support action with frozen parameters
action = await approval_service.create_support_action(
    ticket_id=ticket_uuid,
    action_type="refund",
    params={"amount": 1000, "currency": "RUB"},
    risk_level="high"
)

# Validate parameter integrity
is_valid = await approval_service.validate_params_integrity(action_id)

# Process approval decision
result = await approval_service.process_approval_decision(
    action_id=action_id,
    staff_id="staff_123",
    approved=True,
    decision_reason="Verified refund condition"
)
```

### 8. Staff Approval Engine (`src/services/staff_approval.py`)
Role-based approval management for support staff:

```python
from src.services.staff_approval import StaffApprovalEngine, StaffRole

staff_engine = StaffApprovalEngine()

# Add staff member with roles
staff_engine.add_staff_member(
    staff_id="emp_123",
    roles=[StaffRole.SUPPORT, StaffRole.FINANCE]
)

# Check approval permission
can_approve = staff_engine.can_approve(
    staff_id="emp_123",
    required_role=StaffRole.FINANCE
)

# Create approval card
card = staff_engine.create_approval_card(
    action_id=action_uuid,
    action_type="refund",
    risk_level="high",
    params={"amount": 1000}
)

# Generate Telegram message
message = card.generate_message()
```

**Staff Roles:**
- `SUPPORT` - Can approve low/medium risk actions
- `FINANCE` - Required for financial actions
- `ADMIN` - Can approve all actions including critical


## Mode A (Deterministic Flows) & Mode B (LLM Investigation)

### Mode A: FSM (Finite State Machine) with Staff Approvals

Deterministic state flows with **Staff Approval Engine** for high-risk mutations:

```
INITIAL → GATHERING_INFO → ANALYZING → PROPOSING_SOLUTION
       ↓                                      ↓
    ESCALATED                     WAITING_APPROVAL
                                        ↓
                    (Staff Review) → EXECUTING_ACTION → RESOLVED
```

#### Staff Approval Engine (Mode A)

Core component for managing high-risk mutations with frozen parameters and hashing:

**Key Features:**
- ✅ **Frozen Parameters**: Immutable action snapshots with SHA256 hashing
- ✅ **Auto-Invalidation**: Parameter changes automatically reject approvals
- ✅ **M2M Idempotency**: All external calls include `Idempotency-Key` + `Trace-ID` headers
- ✅ **Reconciliation Handling**: Provider success + local failure → `reconciliation_pending`
- ✅ **Staff Roles**: support, finance, admin with permission checks
- ✅ **Telegram UI**: Inline approval cards with approve/reject/info buttons

**Implemented Flows:**

**Flow 1: Refund & Subscription Deletion**
- User requests refund with evidence
- Backend validates refund conditions (service not started, double charge, etc.)
- Approval card sent to staff chat with frozen parameters
- Staff approves → manually refunds in YooKassa
- Backend verifies refund → soft-deletes subscription (deactivates searches, stops runs, disables auto-renewal)
- Handles reconciliation if provider succeeds but local deletion fails

**Flow 3: Job Vacancy Archival**
- User requests permanent job suppression
- Collects requester type (employer/rights holder/candidate)
- Gathers suppression reason and evidence
- Approval card sent to staff
- Staff approves → M2M call to Jobs API with persistent suppression metadata
- Prevents parser re-indexing and prohibits reactivation

**Documentation:**
See [STAFF_APPROVAL_GUIDE.md](STAFF_APPROVAL_GUIDE.md) for comprehensive implementation details, configuration, and testing scenarios.

### Mode B: LLM Investigation with Human Handoff

For questions outside deterministic Mode A flows, the bot uses RAG-based investigation:

#### RAG Investigation Flow
1. **Query Classification**: Determines access level (public/authenticated)
2. **KB Retrieval**: Retrieves curated knowledge base entries (filtered by version/status)
3. **LLM Analysis**: Generates response using retrieved context
4. **Policy Validation**: Checks confidence threshold
5. **Handoff Detection**: Monitors for 7 escalation triggers

#### Handoff Triggers
The bot automatically escalates to human support when:
1. **Explicit Request**: User asks for human operator ("к оператору", "менеджер")
2. **Identity Not Verified**: User authentication check fails
3. **Money/Legal Issues**: Keywords like "refund", "chargeback", "lawsuit"
4. **Account Security**: Suspected takeover or breach keywords
5. **Data Request**: GDPR/data deletion/export requests
6. **Tool Failure Cascade**: 2+ tool execution failures
7. **Double LLM Failure**: 2+ consecutive LLM generation failures

#### Knowledge Base Management
- **Owner & Version**: Each KB has explicit owner, version, effective/review dates
- **Status Filtering**: Only "active" KB versions are used
- **Date Validation**: KB must be effective_date <= now <= review_date
- **No Draft Content**: Draft/archived KBs are excluded automatically

## Configuration

All configuration is loaded from environment variables via `pydantic-settings`:

```python
from src.core.config import settings

# Access settings
print(settings.telegram_bot_token)
print(settings.database_url)
print(settings.llm_provider)
```

## Database Migrations

Using Alembic for schema management:

```bash
# Create new migration
alembic revision --autogenerate -m "Add new field"

# Apply migrations
alembic upgrade head

# Revert migration
alembic downgrade -1
```

## Logging

Configured via `LOG_LEVEL` environment variable (default: INFO):

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Message")
logger.error("Error occurred")
```

## Security Considerations

1. **Frozen Parameters**: Action parameters are immutable once created
2. **Parameter Hashing**: SHA256 hash ensures data integrity
3. **Idempotency Keys**: UUID-based deduplication for external API calls
4. **Audit Logging**: Complete mutation history for compliance
5. **LLM Read-Only**: No direct database access from LLM
6. **Type Safety**: Full mypy compliance prevents runtime errors

## Testing

```bash
# Run tests (pytest configuration needed)
pytest tests/

# With coverage
pytest --cov=src tests/
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL health
docker-compose ps

# View database logs
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up
```

### Bot Not Responding

```bash
# Check logs
docker-compose logs bot

# Verify Telegram token
docker-compose exec bot python -c "from src.core.config import settings; print(settings.telegram_bot_token)"
```

### LLM Integration Issues

```bash
# Test LLM service
docker-compose exec bot python -c "from src.services.llm import get_llm_service; import asyncio; asyncio.run(get_llm_service().generate_response('test'))"
```

## Contributing

1. Follow Black code style (88 char lines)
2. Add type hints to all functions
3. Write docstrings for public functions
4. Run tests before submitting

## License

MIT

## Support

For issues and questions, create a GitHub issue or contact the team.
