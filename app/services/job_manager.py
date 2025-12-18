"""Job Manager - Track background ingestion tasks."""
import uuid
import time
from typing import Dict, Optional, List
from pydantic import BaseModel

class IngestJob(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    memory_ids: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []
    created_at: float
    updated_at: float

class JobManager:
    """In-memory job tracker for async tasks."""
    _jobs: Dict[str, IngestJob] = {}

    @classmethod
    def create_job(cls) -> str:
        job_id = str(uuid.uuid4())
        now = time.time()
        cls._jobs[job_id] = IngestJob(
            job_id=job_id,
            status="pending",
            created_at=now,
            updated_at=now
        )
        return job_id

    @classmethod
    def update_job(cls, job_id: str, **kwargs):
        if job_id in cls._jobs:
            job = cls._jobs[job_id]
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()

    @classmethod
    def get_job(cls, job_id: str) -> Optional[IngestJob]:
        return cls._jobs.get(job_id)

    @classmethod
    def cleanup_old_jobs(cls, max_age_seconds: int = 3600):
        """Remove jobs older than max_age."""
        now = time.time()
        to_delete = [
            jid for jid, job in cls._jobs.items() 
            if now - job.updated_at > max_age_seconds
        ]
        for jid in to_delete:
            del cls._jobs[jid]
