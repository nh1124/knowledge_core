import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.database import get_db, SessionLocal
from app.services.ai_analyzer import extract_memories
from app.services.memory_manager import MemoryManager
from app.services.job_manager import JobManager
from app.schemas import IngestRequest, IngestResponse
from app.models.enums import Scope
from app.logging_config import get_logger

logger = get_logger("ingest")

router = APIRouter(prefix="/v1", tags=["Ingest"])


async def background_ingest(job_id: str, request: IngestRequest):
    """Process extraction in the background."""
    logger.info(f"Starting background ingest job: {job_id}")
    JobManager.update_job(job_id, status="processing")
    
    # We need a new session for background task
    async with SessionLocal() as db:
        try:
            # Generate ingest ID for tracking
            user_id = request.user_id or uuid.UUID("00000000-0000-0000-0000-000000000001")
            
            # Extract memories from text using AI
            extracted = await extract_memories(request.text, source=request.source)
            
            if not extracted:
                logger.warning(f"No memories extracted for job {job_id}")
                JobManager.update_job(job_id, status="completed", warnings=["No extractable information found"])
                return

            logger.info(f"Extracted {len(extracted)} memories for job {job_id}")

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
                        skip_dedup=request.skip_dedup,
                    )
                    
                    if result["action"] == "created":
                        created_count += 1
                        memory_ids.append(result["memory_id"])
                    elif result["action"] == "updated":
                        updated_count += 1
                        memory_ids.append(result["memory_id"])
                    else:
                        skipped_count += 1
                        
                    if mem.get("confidence", 0.7) < 0.5:
                        warnings.append(f"Low confidence extraction: {mem['content'][:50]}...")
                        
                except Exception as e:
                    warnings.append(f"Error processing memory: {str(e)}")
                
            await db.commit()
            logger.info(f"Job {job_id} completed: {created_count} created, {updated_count} updated, {skipped_count} skipped")
            
            # Update job status
            JobManager.update_job(
                job_id,
                status="completed",
                created_count=created_count,
                updated_count=updated_count,
                skipped_count=skipped_count,
                memory_ids=memory_ids,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Error in background ingest job {job_id}: {str(e)}", exc_info=True)
            JobManager.update_job(job_id, status="failed", errors=[str(e)])


from app.dependencies import resolve_user_id, resolve_scope_and_agent, request_warnings

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_text(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    user_id: uuid.UUID = Depends(resolve_user_id),
    scope_data: tuple = Depends(resolve_scope_and_agent),
) -> IngestResponse:
    """Analyze raw text in the background and create memories."""
    # Use resolved values
    scope, agent_id = scope_data
    request.user_id = user_id
    request.scope = scope
    request.agent_id = agent_id

    job_id = JobManager.create_job()
    background_tasks.add_task(background_ingest, job_id, request)
    
    warnings = ["Processing started in background"]
    warnings.extend(request_warnings.get())

    return IngestResponse(
        ingest_id=job_id,
        created_count=0,
        updated_count=0,
        skipped_count=0,
        memory_ids=[],
        warnings=warnings
    )


@router.get("/ingest/{job_id}")
async def get_ingest_status(job_id: str):
    """Get status of an ingestion job."""
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
