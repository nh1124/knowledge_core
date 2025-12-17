"""Memory Pydantic models for API requests/responses."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import MemoryType, Scope, InputChannel


class MemoryBase(BaseModel):
    """Base memory model with common fields."""
    content: str = Field(..., description="Knowledge content")
    memory_type: MemoryType = Field(..., description="Type of memory")
    tags: list[str] = Field(default_factory=list, description="Classification tags")
    scope: Scope = Field(default=Scope.GLOBAL, description="Visibility scope")
    agent_id: Optional[str] = Field(None, description="Target agent for agent scope")
    importance: int = Field(default=3, ge=1, le=5, description="Priority 1-5")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence score")
    related_entities: Optional[dict] = Field(None, description="Related entity references")
    source: Optional[str] = Field(None, description="Information source")


class MemoryCreate(MemoryBase):
    """Model for creating a new memory."""
    user_id: Optional[UUID] = Field(None, description="Owner user ID")
    input_channel: InputChannel = Field(default=InputChannel.API)
    event_time: Optional[datetime] = Field(None, description="When event occurred")


class MemoryUpdate(BaseModel):
    """Model for updating an existing memory."""
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: Optional[int] = Field(None, ge=1, le=5)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    related_entities: Optional[dict] = None


class Memory(MemoryBase):
    """Full memory model for API responses."""
    id: UUID
    user_id: UUID
    input_channel: Optional[InputChannel] = None
    content_hash: Optional[str] = None
    event_time: Optional[datetime] = None
    valid_from: datetime
    valid_to: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    supersedes_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemoryInDB(Memory):
    """Memory model with embedding (internal use)."""
    embedding: Optional[list[float]] = None
