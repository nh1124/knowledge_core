"""Context router - POST /v1/context for RAG-based context synthesis."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db
from app.services.memory_manager import MemoryManager
from app.services.ai_analyzer import synthesize_context
from app.dependencies import resolve_user_id, resolve_scope_and_agent, request_warnings, require_scope
from app.schemas import ContextRequest, ContextResponse, ContextEvidenceItem, ScoreComponents
from app.auth import Identity, resolve_identity

router = APIRouter(prefix="/v1", tags=["Context"])

@router.post("/context", response_model=ContextResponse)
async def get_context(
    request: ContextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(resolve_user_id),
    scope_data: tuple = Depends(resolve_scope_and_agent),
    identity: Identity = Depends(require_scope("context")),
) -> ContextResponse:
    """Synthesize context from relevant memories using RAG.
    
    Process:
    1. Vector search to find relevant memories
    2. Re-rank by importance, recency, and confidence
    3. AI synthesizes a context summary for the calling agent
    """
    scope, agent_id = scope_data
    manager = MemoryManager(db)
    
    # AI Analysis Settings
    llm_model: str = "models/gemini-2.5-flash-lite"
    
    # Get user's Gemini API key
    api_key = identity.gemini_api_key
    
    # Search for relevant memories (with user's key for embedding)
    memories = await manager.search_memories(
        user_id=user_id,
        query=request.query,
        scope=scope,
        agent_id=agent_id,
        include_global=request.include_global,
        limit=request.k,
        api_key=api_key,
    )
    
    if not memories:
        return ContextResponse(
            context={
                "summary": "No relevant memories found for this query.",
                "bullets": [],
            },
            evidence=[] if request.return_evidence else None,
            warnings=request_warnings.get()
        )
    
    # Synthesize context using AI (with user's key)
    context = await synthesize_context(
        query=request.query,
        memories=memories,
        app_context=request.app_context,
        api_key=api_key,
    )
    
    # Build evidence list if requested
    evidence = None
    if request.return_evidence:
        evidence = [
            ContextEvidenceItem(
                memory_id=m["id"],
                similarity=m.get("similarity") or 0.0,
                final_score=m.get("score") or 0.0,
                content=m["content"],
                score_components=ScoreComponents(
                    importance=m.get("score_components", {}).get("importance", 0.0),
                    confidence=m.get("score_components", {}).get("confidence", 0.0),
                    recency_factor=m.get("score_components", {}).get("recency_factor", 1.0),
                ) if "score_components" in m else None
            )
            for m in memories
        ]
    
    return ContextResponse(
        context=context,
        evidence=evidence,
        warnings=request_warnings.get()
    )
