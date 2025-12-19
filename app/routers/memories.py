"""Memories router - CRUD operations for memories."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db
from app.services.memory_manager import MemoryManager
from app.schemas import (
    MemoryCreateRequest, 
    MemoryUpdateRequest, 
    MemoryResponse, 
    MemoryListResponse,
)
from app.models.enums import MemoryType, Scope
from app.dependencies import resolve_user_id, resolve_scope_and_agent, request_warnings, require_scope

router = APIRouter(prefix="/v1", tags=["Memories"])


@router.post("/memories", response_model=MemoryResponse)
async def create_memory(
    request: MemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(resolve_user_id),
    scope_data: tuple = Depends(resolve_scope_and_agent),
    _identity = Depends(require_scope("memories:write")),
) -> MemoryResponse:
    """Force/manual ingest - bypass AI analysis and directly create a memory.
    
    Use this for:
    - FACT registration that should not be modified by AI
    - API keys, configuration, or high-risk information
    """
    scope, agent_id = scope_data
    manager = MemoryManager(db)
    
    result = await manager.create_memory(
        content=request.content,
        memory_type=request.memory_type,
        user_id=user_id,
        tags=request.tags,
        scope=scope,
        agent_id=agent_id,
        importance=request.importance,
        confidence=request.confidence,
        source=request.source or "manual",
        input_channel="manual",
        skip_dedup=request.skip_dedup,
    )
    
    # Fetch the created memory
    memory = await manager.get_memory(uuid.UUID(result["memory_id"]), user_id=user_id)
    if not memory:
        raise HTTPException(status_code=500, detail="Failed to create memory")
    
    response = MemoryResponse(**memory)
    response.warnings = request_warnings.get()
    return response


@router.get("/memories", response_model=MemoryListResponse)
async def list_memories(
    memory_type: Optional[MemoryType] = Query(None, description="Memory type filter"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    q: Optional[str] = Query(None, description="Search query (vector similarity)"),
    limit: int = Query(50, ge=1, le=100, description="Result limit"),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(resolve_user_id),
    scope_data: tuple = Depends(resolve_scope_and_agent),
    _identity = Depends(require_scope("memories:read")),
) -> MemoryListResponse:
    """Search and retrieve memories.
    
    Supports:
    - Tag filtering
    - Memory type filtering
    - Scope filtering
    - Full-text/vector similarity search with 'q' parameter
    """
    scope, agent_id = scope_data
    manager = MemoryManager(db)
    
    # Parse tags
    tag_list = tags.split(",") if tags else None
    
    memories = await manager.search_memories(
        user_id=user_id,
        query=q,
        tags=tag_list,
        memory_type=memory_type,
        scope=scope,
        agent_id=agent_id,
        limit=limit,
    )
    
    return MemoryListResponse(
        memories=[MemoryResponse(**m) for m in memories],
        total=len(memories),
        warnings=request_warnings.get()
    )


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(resolve_user_id),
    _identity = Depends(require_scope("memories:read")),
) -> MemoryResponse:
    """Get a single memory by ID."""
    manager = MemoryManager(db)
    
    try:
        mid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory ID format")
    
    memory = await manager.get_memory(mid, user_id=user_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    response = MemoryResponse(**memory)
    response.warnings = request_warnings.get()
    return response


@router.patch("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(resolve_user_id),
    _identity = Depends(require_scope("memories:write")),
) -> MemoryResponse:
    """Update a memory's content, tags, importance, or confidence."""
    manager = MemoryManager(db)
    
    try:
        mid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory ID format")
    
    updated = await manager.update_memory(
        memory_id=mid,
        user_id=user_id,
        content=request.content,
        tags=request.tags,
        importance=request.importance,
        confidence=request.confidence,
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    response = MemoryResponse(**updated)
    response.warnings = request_warnings.get()
    return response


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    hard: bool = Query(False, description="Hard delete (permanent)"),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(resolve_user_id),
    _identity = Depends(require_scope("memories:write")),
):
    """Delete a memory (soft delete by default)."""
    manager = MemoryManager(db)
    
    try:
        mid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory ID format")
    
    deleted = await manager.delete_memory(mid, user_id=user_id, hard_delete=hard)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {
        "status": "deleted", 
        "memory_id": memory_id,
        "warnings": request_warnings.get()
    }


@router.get("/dump")
async def dump_memories(
    format: str = Query("json", description="Output format (json/jsonl)"),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(resolve_user_id),
    scope_data: tuple = Depends(resolve_scope_and_agent),
    _identity = Depends(require_scope("dump")),
):
    """Export all memories (admin endpoint).
    
    Returns all memories matching the filters in JSON or JSONL format.
    """
    scope, agent_id = scope_data
    manager = MemoryManager(db)
    
    memories = await manager.search_memories(
        user_id=user_id,
        scope=scope,
        agent_id=agent_id,
        limit=1000,  # Higher limit for dump
    )
    
    # For JSONL, each memory would be a separate line
    # For now, return as JSON array
    return {
        "format": format,
        "count": len(memories),
        "memories": memories,
        "warnings": request_warnings.get()
    }
