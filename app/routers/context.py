"""Context router - POST /v1/context for RAG-based context synthesis."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db
from app.services.memory_manager import MemoryManager
from app.services.ai_analyzer import synthesize_context
from app.schemas import ContextRequest, ContextResponse, ContextEvidenceItem

router = APIRouter(prefix="/v1", tags=["Context"])


@router.post("/context", response_model=ContextResponse)
async def get_context(
    request: ContextRequest,
    db: AsyncSession = Depends(get_db),
) -> ContextResponse:
    """Synthesize context from relevant memories using RAG.
    
    Process:
    1. Vector search to find relevant memories
    2. Re-rank by importance, recency, and confidence
    3. AI synthesizes a context summary for the calling agent
    """
    # Use default user_id if not provided
    user_id = request.user_id or uuid.UUID("00000000-0000-0000-0000-000000000001")
    
    manager = MemoryManager(db)
    
    # Search for relevant memories
    memories = await manager.search_memories(
        user_id=user_id,
        query=request.query,
        scope=request.scope,
        agent_id=request.agent_id,
        include_global=request.include_global,
        limit=request.k,
    )
    
    if not memories:
        return ContextResponse(
            context={
                "summary": "No relevant memories found for this query.",
                "bullets": [],
            },
            evidence=[] if request.return_evidence else None,
        )
    
    # Synthesize context using AI
    context = await synthesize_context(
        query=request.query,
        memories=memories,
        app_context=request.app_context,
    )
    
    # Build evidence list if requested
    evidence = None
    if request.return_evidence:
        evidence = [
            ContextEvidenceItem(
                memory_id=m["id"],
                score=m.get("similarity", 0.0),
                content=m["content"],
            )
            for m in memories
        ]
    
    return ContextResponse(
        context=context,
        evidence=evidence,
    )
