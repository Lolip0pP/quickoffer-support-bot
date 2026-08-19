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

- `/start` - Start the bot
- `/help` - Show help message
- `/issue` - Report a new issue
- `/status` - Check ticket status
- `/cancel` - Cancel current operation

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

## LLM Service

LLM is **read-only** to prevent unauthorized mutations:

```python
from src.services.llm import get_llm_service

llm = get_llm_service()

# Read-only operations
response = await llm.generate_response(prompt)
analysis = await llm.analyze_ticket(content)
suggestion = await llm.suggest_resolution(ticket_id)
```

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
