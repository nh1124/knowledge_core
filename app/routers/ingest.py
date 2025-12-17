"""Ingest router - POST /v1/ingest for text analysis and memory creation."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db
from app.services.ai_analyzer import extract_memories
from app.services.memory_manager import MemoryManager
from app.schemas import IngestRequest, IngestResponse
from app.models.enums import Scope

router = APIRouter(prefix="/v1", tags=["Ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_text(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Analyze raw text and create structured memories.
    
    The AI will:
    1. Extract atomic pieces of information from the text
    2. Classify each as FACT, STATE, EPISODE, or POLICY
    3. Assign tags, importance, and confidence scores
    4. Check for duplicates and apply upsert strategies
    """
    # Generate ingest ID for tracking
    ingest_id = str(uuid.uuid4())
    
    # Use default user_id if not provided (for development)
    user_id = request.user_id or uuid.UUID("00000000-0000-0000-0000-000000000001")
    
    # Extract memories from text using AI
    extracted = await extract_memories(request.text, source=request.source)
    
    if not extracted:
        return IngestResponse(
            ingest_id=ingest_id,
            created_count=0,
            updated_count=0,
            skipped_count=0,
            memory_ids=[],
            warnings=["No extractable information found in input"],
        )
    
    # Create memories using Memory Manager
    manager = MemoryManager(db)
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    memory_ids = []
    warnings = []
    
    for mem in extracted:
        try:
            result = await manager.create_memory(
                content=mem["content"],
                memory_type=mem["memory_type"],
                user_id=user_id,
                tags=mem.get("tags", []),
                scope=request.scope,
                agent_id=request.agent_id,
                importance=mem.get("importance", 3),
                confidence=mem.get("confidence", 0.7),
                source=request.source,
                input_channel="chat" if request.source == "chat" else "api",
                event_time=request.event_time,
            )
            
            if result["action"] == "created":
                created_count += 1
                memory_ids.append(result["memory_id"])
            elif result["action"] == "updated":
                updated_count += 1
                memory_ids.append(result["memory_id"])
            else:
                skipped_count += 1
                
            # Add warning for low confidence
            if mem.get("confidence", 0.7) < 0.5:
                warnings.append(f"Low confidence extraction: {mem['content'][:50]}...")
                
        except Exception as e:
            warnings.append(f"Error processing memory: {str(e)}")
    
    return IngestResponse(
        ingest_id=ingest_id,
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        memory_ids=memory_ids,
        warnings=warnings,
    )
