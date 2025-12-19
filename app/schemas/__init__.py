"""API request/response schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import MemoryType, Scope, InputChannel


# ==================== Ingest Schemas ====================

class IngestRequest(BaseModel):
    """Request body for POST /v1/ingest."""
    text: str = Field(..., description="Input text to analyze")
    source: str = Field(..., description="Input source (chat, manual, api, etc.)")
    user_id: Optional[UUID] = Field(None, description="User identifier")
    agent_id: Optional[str] = Field(None, description="Calling agent/client ID")
    scope: Scope = Field(default=Scope.GLOBAL, description="Memory scope")
    event_time: Optional[datetime] = Field(None, description="Event occurrence time")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class IngestResponse(BaseModel):
    """Response body for POST /v1/ingest."""
    ingest_id: str = Field(..., description="Ingest job ID")
    created_count: int = Field(0, description="Number of new memories")
    updated_count: int = Field(0, description="Number of updated memories")
    skipped_count: int = Field(0, description="Number of skipped duplicates")
    memory_ids: list[str] = Field(default_factory=list, description="Created memory IDs")
    warnings: list[str] = Field(default_factory=list, description="Warnings/conflicts")


# ==================== Memory CRUD Schemas ====================

class MemoryCreateRequest(BaseModel):
    """Request body for POST /v1/memories (force ingest)."""
    content: str = Field(..., description="Memory content")
    memory_type: MemoryType = Field(..., description="Memory type")
    tags: list[str] = Field(default_factory=list, description="Tags")
    user_id: Optional[UUID] = Field(None, description="User identifier")
    agent_id: Optional[str] = Field(None, description="Agent/client ID")
    scope: Scope = Field(default=Scope.GLOBAL, description="Visibility scope")
    importance: int = Field(default=3, ge=1, le=5, description="Priority 1-5")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence")
    source: Optional[str] = Field(None, description="Information source")


class MemoryUpdateRequest(BaseModel):
    """Request body for PATCH /v1/memories/{id}."""
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: Optional[int] = Field(None, ge=1, le=5)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    """Response body for memory endpoints."""
    id: str
    user_id: str
    content: str
    memory_type: str
    tags: list[str]
    scope: str
    agent_id: Optional[str] = None
    importance: int
    confidence: float
    source: Optional[str] = None
    event_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryListResponse(BaseModel):
    """Response for GET /v1/memories."""
    memories: list[MemoryResponse]
    total: int
    cursor: Optional[str] = None


# ==================== Context (RAG) Schemas ====================

class ContextRequest(BaseModel):
    """Request body for POST /v1/context."""
    query: str = Field(..., description="Current query/question")
    app_context: Optional[dict] = Field(None, description="Application state")
    user_id: Optional[UUID] = Field(None, description="User identifier")
    agent_id: Optional[str] = Field(None, description="Calling agent ID")
    scope: Scope = Field(default=Scope.GLOBAL, description="Memory scope")
    k: int = Field(default=10, ge=1, le=50, description="Number of memories to retrieve")
    include_global: bool = Field(default=True, description="Include global scope for agent")
    return_evidence: bool = Field(default=False, description="Return source memory IDs")


class ContextEvidenceItem(BaseModel):
    """Evidence item in context response."""
    memory_id: str
    score: float
    content: str


class ContextResponse(BaseModel):
    """Response body for POST /v1/context."""
    context: dict = Field(..., description="Synthesized context with summary and bullets")
    evidence: Optional[list[ContextEvidenceItem]] = Field(None, description="Source memories")


# ==================== Error Schemas ====================

class ErrorDetail(BaseModel):
    """Error detail."""
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: ErrorDetail
