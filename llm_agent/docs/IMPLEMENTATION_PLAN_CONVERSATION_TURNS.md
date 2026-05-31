# Implementation Plan: Conversation & Turn Layer

> **Prerequisites**: Ensure you've read [DOMAIN_VOCABULARY.md](./DOMAIN_VOCABULARY.md) for the target design.

## Overview

This plan covers implementing the Conversation/Turn abstraction layer on top of the existing Run infrastructure. The goal is to provide a user-friendly API for chat-based interactions while preserving the operational Run model for backend processing.

---

## Phase 1: Domain Models

### 1.1 Create Conversation Domain Model

**File**: `llm_agent/llm_agent/domain/conversation/conversation.py`

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class Conversation:
    id: UUID
    created_at: datetime
    metadata: dict | None = None
```

### 1.2 Create Turn Domain Model

**File**: `llm_agent/llm_agent/domain/conversation/turn.py`

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

class TurnRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"

class AssistantTurnStatus(Enum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass(frozen=True)
class Turn:
    id: UUID
    conversation_id: UUID
    role: TurnRole
    content: str | None  # None for pending assistant turns
    parent_turn_id: UUID | None  # For branching
    created_at: datetime
    status: AssistantTurnStatus | None  # Only for assistant turns
    run_id: UUID | None  # Only for assistant turns
```

### 1.3 Create Turn-Run Mapping

**File**: `llm_agent/llm_agent/domain/conversation/status_mapper.py`

```python
from contracts.domain.runs.status_code import RunStatusCode
from llm_agent.domain.conversation.turn import AssistantTurnStatus

def run_status_to_turn_status(run_status: RunStatusCode) -> AssistantTurnStatus:
    """Map internal run status to user-facing turn status."""
    mapping = {
        RunStatusCode.CREATED: AssistantTurnStatus.PENDING,
        RunStatusCode.ENQUEUED: AssistantTurnStatus.PENDING,
        RunStatusCode.RUNNING: AssistantTurnStatus.STREAMING,
        RunStatusCode.SUCCEEDED: AssistantTurnStatus.COMPLETED,
        RunStatusCode.FAILED: AssistantTurnStatus.FAILED,
        RunStatusCode.TIMED_OUT: AssistantTurnStatus.FAILED,
        RunStatusCode.CANCELLED: AssistantTurnStatus.CANCELLED,
        RunStatusCode.RETRYING: AssistantTurnStatus.PENDING,
    }
    return mapping[run_status]
```

**Estimated effort**: 2-3 hours

---

## Phase 2: Repository Layer

### 2.1 Define Repository Interfaces

**File**: `llm_agent/llm_agent/domain/conversation/repository.py`

```python
from abc import ABC, abstractmethod
from uuid import UUID
from llm_agent.domain.conversation.conversation import Conversation
from llm_agent.domain.conversation.turn import Turn

class ConversationRepository(ABC):
    @abstractmethod
    async def create(self, conversation: Conversation) -> Conversation: ...
    
    @abstractmethod
    async def get(self, conversation_id: UUID) -> Conversation | None: ...
    
    @abstractmethod
    async def delete(self, conversation_id: UUID) -> bool: ...

class TurnRepository(ABC):
    @abstractmethod
    async def create(self, turn: Turn) -> Turn: ...
    
    @abstractmethod
    async def get(self, turn_id: UUID) -> Turn | None: ...
    
    @abstractmethod
    async def list_by_conversation(
        self, 
        conversation_id: UUID, 
        limit: int = 100,
        before_turn_id: UUID | None = None
    ) -> list[Turn]: ...
    
    @abstractmethod
    async def update_status(
        self, 
        turn_id: UUID, 
        status: AssistantTurnStatus,
        content: str | None = None
    ) -> Turn: ...
    
    @abstractmethod
    async def get_assistant_turns_for_user_turn(
        self, 
        user_turn_id: UUID
    ) -> list[Turn]: ...
```

### 2.2 In-Memory Implementation (for development/testing)

**File**: `llm_agent/llm_agent/repositories/in_memory/conversation.py`

```python
class InMemoryConversationRepository(ConversationRepository):
    def __init__(self):
        self._conversations: dict[UUID, Conversation] = {}
    
    # ... implement methods
```

### 2.3 Database Implementation (Piccolo ORM)

**Files**:
- `llm_agent/llm_agent/repositories/piccolo/tables/conversation.py`
- `llm_agent/llm_agent/repositories/piccolo/tables/turn.py`
- `llm_agent/llm_agent/repositories/piccolo/conversation_repository.py`

**Estimated effort**: 4-6 hours

---

## Phase 3: Service Layer

### 3.1 Conversation Service

**File**: `llm_agent/llm_agent/services/conversation/service.py`

```python
class ConversationService:
    def __init__(
        self,
        conversation_repo: ConversationRepository,
        turn_repo: TurnRepository,
        run_orchestrator: BackendRunOrchestrationService,
        idempotency_store: IdempotencyStore,
    ):
        ...
    
    async def create_conversation(
        self, 
        metadata: dict | None = None
    ) -> Conversation:
        """Create a new conversation."""
        ...
    
    async def create_user_turn(
        self,
        conversation_id: UUID,
        content: str,
        idempotency_key: str | None = None,
    ) -> tuple[Turn, Turn, RunStatus]:
        """
        Create a user turn, which automatically creates:
        1. The user turn
        2. A pending assistant turn
        3. A run to produce the assistant response
        
        Returns (user_turn, assistant_turn, run)
        """
        ...
    
    async def get_turns(
        self,
        conversation_id: UUID,
        limit: int = 100,
        before_turn_id: UUID | None = None,
    ) -> list[Turn]:
        """List turns in a conversation."""
        ...
    
    async def regenerate(
        self,
        user_turn_id: UUID,
    ) -> tuple[Turn, RunStatus]:
        """
        Create a new assistant turn attempt for an existing user turn.
        Returns (new_assistant_turn, new_run)
        """
        ...
```

### 3.2 Idempotency Store

**File**: `llm_agent/llm_agent/services/idempotency/store.py`

```python
class IdempotencyStore(ABC):
    @abstractmethod
    async def get_or_set(
        self, 
        key: str, 
        request_hash: str,
        ttl_seconds: int = 86400  # 24 hours
    ) -> tuple[bool, Any | None]:
        """
        Returns (is_duplicate, cached_response)
        If not duplicate, stores the key and returns (False, None)
        """
        ...
    
    @abstractmethod
    async def set_response(self, key: str, response: Any) -> None:
        """Store the response for a completed request."""
        ...
```

**Estimated effort**: 6-8 hours

---

## Phase 4: API Layer

### 4.1 DTOs

**File**: `llm_agent/llm_agent/api/http/v1/dto/conversation.py`

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class CreateConversationRequestDto(BaseModel):
    metadata: dict | None = None

class ConversationDto(BaseModel):
    id: UUID
    created_at: datetime
    metadata: dict | None = None

class TurnDto(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str  # "user" | "assistant"
    content: str | None
    status: str | None  # Only for assistant turns
    run_id: UUID | None
    parent_turn_id: UUID | None
    created_at: datetime

class CreateUserTurnRequestDto(BaseModel):
    content: str

class CreateUserTurnResponseDto(BaseModel):
    user_turn: TurnDto
    assistant_turn: TurnDto
    run: RunDto

class TurnListResponseDto(BaseModel):
    turns: list[TurnDto]
    has_more: bool

class RegenerateResponseDto(BaseModel):
    assistant_turn: TurnDto
    run: RunDto
```

### 4.2 Routes

**File**: `llm_agent/llm_agent/api/http/v1/routes/conversations.py`

```python
from fastapi import APIRouter, Header

conversation_router = APIRouter()

@conversation_router.post("/conversations")
async def create_conversation(
    request: CreateConversationRequestDto,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationDto:
    ...

@conversation_router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationDto:
    ...

@conversation_router.post("/conversations/{conversation_id}/turns")
async def create_user_turn(
    conversation_id: UUID,
    request: CreateUserTurnRequestDto,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    service: ConversationService = Depends(get_conversation_service),
) -> CreateUserTurnResponseDto:
    ...

@conversation_router.get("/conversations/{conversation_id}/turns")
async def list_turns(
    conversation_id: UUID,
    limit: int = Query(100, le=200),
    before: UUID | None = Query(None),
    service: ConversationService = Depends(get_conversation_service),
) -> TurnListResponseDto:
    ...

@conversation_router.post("/turns/{user_turn_id}:regenerate")
async def regenerate_turn(
    user_turn_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
) -> RegenerateResponseDto:
    ...

@conversation_router.post("/turns/{assistant_turn_id}:cancel")
async def cancel_turn(
    assistant_turn_id: UUID,
    service: ConversationService = Depends(get_conversation_service),
) -> CancelRunResponseDto:
    """Facade that cancels the underlying run."""
    ...
```

### 4.3 Register Routes

**File**: `llm_agent/llm_agent/api/http/v1/routes/__init__.py`

```python
from llm_agent.api.http.v1.routes.conversations import conversation_router

# Add to main router
api_v1_router.include_router(conversation_router, tags=["conversations"])
```

**Estimated effort**: 4-6 hours

---

## Phase 5: Worker Integration

### 5.1 Update Run Completion Handler

When a run completes, update the corresponding assistant turn:

**File**: `llm_agent/agent_run_worker/services/runs/completion_handler.py`

```python
class RunCompletionHandler:
    def __init__(
        self,
        turn_repo: TurnRepository,
    ):
        ...
    
    async def on_run_completed(
        self, 
        run_id: UUID, 
        result: dict,
    ) -> None:
        """Update assistant turn when run succeeds."""
        turn = await self.turn_repo.get_by_run_id(run_id)
        if turn:
            await self.turn_repo.update_status(
                turn.id,
                AssistantTurnStatus.COMPLETED,
                content=result.get("response"),
            )
    
    async def on_run_failed(
        self, 
        run_id: UUID, 
        error: str,
    ) -> None:
        """Update assistant turn when run fails."""
        ...
    
    async def on_run_cancelled(
        self, 
        run_id: UUID,
    ) -> None:
        """Update assistant turn when run is cancelled."""
        ...
```

**Estimated effort**: 2-3 hours

---

## Phase 6: Database Migrations

### 6.1 Create Migration Scripts

**Piccolo migrations** for:
- `conversations` table
- `turns` table  
- `idempotency_keys` table

```sql
-- conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

-- turns
CREATE TABLE turns (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT,
    status VARCHAR(20),  -- NULL for user turns
    run_id UUID,  -- NULL for user turns
    parent_turn_id UUID REFERENCES turns(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_turns_conversation ON turns(conversation_id, created_at);
CREATE INDEX idx_turns_run ON turns(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX idx_turns_parent ON turns(parent_turn_id) WHERE parent_turn_id IS NOT NULL;

-- idempotency_keys
CREATE TABLE idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    request_hash VARCHAR(64) NOT NULL,
    response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_idempotency_expires ON idempotency_keys(expires_at);
```

**Estimated effort**: 2-3 hours

---

## Phase 7: DI Registration

### 7.1 Create Registrar

**File**: `llm_agent/llm_agent/di/registrars/conversation.py`

```python
from llm_agent.di.registrars.base import Registrar

class ConversationRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_factory(
            ConversationRepository,
            self._create_conversation_repo,
        )
        registry.register_factory(
            TurnRepository,
            self._create_turn_repo,
        )
        registry.register_factory(
            ConversationService,
            self._create_conversation_service,
        )
```

**Estimated effort**: 1-2 hours

---

## Phase 8: Testing

### 8.1 Unit Tests

- Domain model tests (status mapping, validation)
- Service layer tests (with mocked repositories)
- Idempotency logic tests

### 8.2 Integration Tests

**File**: `llm_agent/tests/thin_integration/test_conversation_flow.py`

```python
async def test_create_conversation_and_turns():
    """Full flow: create conversation, add turn, poll for completion."""
    ...

async def test_idempotent_turn_creation():
    """Same idempotency key returns same response."""
    ...

async def test_regenerate_creates_new_attempt():
    """Regenerate creates new assistant turn for same user turn."""
    ...

async def test_cancel_via_turn_id():
    """Cancel using assistant turn ID facade."""
    ...
```

**Estimated effort**: 4-6 hours

---

## Implementation Order (Recommended)

| Week | Phase | Deliverable |
|------|-------|-------------|
| 1 | Phase 1-2 | Domain models + In-memory repositories |
| 1 | Phase 6 | Database migrations (can run in parallel) |
| 2 | Phase 3 | Service layer with business logic |
| 2 | Phase 4 | API endpoints |
| 3 | Phase 5 | Worker integration |
| 3 | Phase 7-8 | DI registration + Testing |

**Total estimated effort**: 25-35 hours

---

## Migration Path (Existing Clients)

1. **v1.0**: Deploy new endpoints alongside existing `/runs` endpoints
2. **v1.1**: Deprecation warnings on direct `/runs` usage for chat flows
3. **v2.0**: Remove direct run creation (keep `GET /runs/{id}` for operational visibility)

Existing `/runs` endpoints remain available for:
- Operational monitoring
- Background jobs (non-conversational)
- Legacy client support during migration

---

## Open Questions

1. **Streaming**: Should we implement SSE endpoints for real-time token streaming?
   - `GET /runs/{run_id}/events:stream` (Server-Sent Events)
   
2. **Branching UI**: How should the API support edit/branch scenarios?
   - Currently: `parent_turn_id` on turns
   - Alternative: Explicit branch endpoint
   
3. **Conversation deletion**: Soft delete vs hard delete? Cascade to turns/runs?

4. **Rate limiting**: Per-conversation or per-user limits?
