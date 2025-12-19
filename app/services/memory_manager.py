"""Memory Manager - Core logic for memory CRUD and deduplication."""
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MemoryType, Scope, AuditAction, ActorType
from app.services.embedding import generate_embedding, compute_content_hash
from app.config import get_settings

settings = get_settings()


def _format_embedding(embedding: list[float]) -> str:
    """Format embedding list as PostgreSQL vector string literal."""
    # PostgreSQL pgvector expects format: '[0.1,0.2,...]'
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def _format_jsonb(data: Optional[dict]) -> Optional[str]:
    """Format dict as JSON string for JSONB column."""
    if data is None:
        return None
    return json.dumps(data)


class MemoryManager:
    """Core memory management logic with deduplication and upsert strategies."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def _apply_rls(self, user_id: uuid.UUID):
        """Set session variable for PostgreSQL RLS."""
        await self.session.execute(
            text("SELECT set_config('app.current_user_id', :uid, true)"),
            {"uid": str(user_id)}
        )

    async def create_memory(
        self,
        content: str,
        memory_type: MemoryType,
        user_id: uuid.UUID,
        tags: list[str] = None,
        scope: Scope = Scope.GLOBAL,
        agent_id: Optional[str] = None,
        importance: int = 3,
        confidence: float = 0.7,
        source: Optional[str] = None,
        input_channel: str = "api",
        event_time: Optional[datetime] = None,
        related_entities: Optional[dict] = None,
        skip_dedup: bool = False,
    ) -> dict:
        """Create a new memory with deduplication check.
        
        Returns:
            dict with keys: action (created/updated/skipped), memory_id, message
        """
        # Set RLS context
        await self._apply_rls(user_id)
        
        tags = tags or []
        content_hash = compute_content_hash(content)
        
        # Check for existing memory by content hash
        existing = await self._find_by_hash(user_id, scope, agent_id, content_hash)
        if existing and not skip_dedup:
            return {
                "action": "skipped",
                "memory_id": existing["id"],
                "message": "Duplicate content detected",
            }
        
        # Generate embedding
        embedding = await generate_embedding(content)
        
        # Check for similar memory (vector search)
        if not skip_dedup:
            similar = await self._find_similar(
                embedding, user_id, scope, agent_id, memory_type
            )
            if similar:
                # Apply upsert strategy based on memory type
                return await self._apply_upsert_strategy(
                    similar, content, memory_type, embedding, content_hash, tags, importance, confidence
                )
        
        # Insert new memory
        memory_id = uuid.uuid4()
        await self.session.execute(
            text("""
                INSERT INTO memories (
                    id, user_id, content, embedding, memory_type, tags, scope, agent_id,
                    importance, confidence, source, input_channel, content_hash,
                    event_time, related_entities
                ) VALUES (
                    :id, :user_id, :content, :embedding, :memory_type, :tags, :scope, :agent_id,
                    :importance, :confidence, :source, :input_channel, :content_hash,
                    :event_time, :related_entities
                )
            """),
            {
                "id": memory_id,
                "user_id": user_id,
                "content": content,
                "embedding": _format_embedding(embedding),
                "memory_type": memory_type.value,
                "tags": tags,
                "scope": scope.value,
                "agent_id": agent_id,
                "importance": importance,
                "confidence": confidence,
                "source": source,
                "input_channel": input_channel,
                "content_hash": content_hash,
                "event_time": event_time,
                "related_entities": _format_jsonb(related_entities),
            }
        )
        
        # Create audit log
        await self._create_audit_log(memory_id, AuditAction.CREATE)
        
        return {
            "action": "created",
            "memory_id": str(memory_id),
            "message": "Memory created successfully",
        }
    
    async def _find_by_hash(
        self, user_id: uuid.UUID, scope: Scope, agent_id: Optional[str], content_hash: str
    ) -> Optional[dict]:
        """Find memory by content hash for exact deduplication."""
        result = await self.session.execute(
            text("""
                SELECT id, content, memory_type FROM memories
                WHERE user_id = :user_id 
                AND scope = :scope 
                AND COALESCE(agent_id, '') = COALESCE(:agent_id, '')
                AND content_hash = :content_hash
                AND valid_to IS NULL
                LIMIT 1
            """),
            {
                "user_id": user_id,
                "scope": scope.value,
                "agent_id": agent_id,
                "content_hash": content_hash,
            }
        )
        row = result.fetchone()
        if row:
            return {"id": str(row[0]), "content": row[1], "memory_type": row[2]}
        return None
    
    async def _find_similar(
        self,
        embedding: list[float],
        user_id: uuid.UUID,
        scope: Scope,
        agent_id: Optional[str],
        memory_type: MemoryType,
    ) -> Optional[dict]:
        """Find similar memory using vector similarity search."""
        # Only check similarity for FACT and STATE (EPISODE always appends)
        if memory_type == MemoryType.EPISODE:
            return None
        
        result = await self.session.execute(
            text("""
                SELECT id, content, memory_type, 
                       1 - (embedding <=> CAST(:embedding AS vector)) as similarity
                FROM memories
                WHERE user_id = :user_id 
                AND scope = :scope 
                AND COALESCE(agent_id, '') = COALESCE(:agent_id, '')
                AND memory_type = :memory_type
                AND valid_to IS NULL
                AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT 1
            """),
            {
                "embedding": _format_embedding(embedding),
                "user_id": user_id,
                "scope": scope.value,
                "agent_id": agent_id,
                "memory_type": memory_type.value,
            }
        )
        row = result.fetchone()
        if row and row[3] >= settings.similarity_threshold:
            return {
                "id": str(row[0]),
                "content": row[1],
                "memory_type": row[2],
                "similarity": row[3],
            }
        return None
    
    async def _apply_upsert_strategy(
        self,
        existing: dict,
        new_content: str,
        memory_type: MemoryType,
        embedding: list[float],
        content_hash: str,
        tags: list[str],
        importance: int,
        confidence: float,
    ) -> dict:
        """Apply upsert strategy based on memory type.
        
        - FACT/STATE: Invalidate old, create new with supersedes_id
        - EPISODE: Should not reach here (always append)
        """
        existing_id = uuid.UUID(existing["id"])
        
        # Invalidate existing memory
        await self.session.execute(
            text("""
                UPDATE memories SET valid_to = NOW(), updated_at = NOW()
                WHERE id = :id
            """),
            {"id": existing_id}
        )
        
        # Create new memory with supersedes_id
        new_id = uuid.uuid4()
        result = await self.session.execute(
            text("""
                INSERT INTO memories (
                    id, user_id, content, embedding, memory_type, tags, scope, agent_id,
                    importance, confidence, content_hash, supersedes_id
                )
                SELECT :new_id, user_id, :content, CAST(:embedding AS vector), memory_type, 
                       :tags, scope, agent_id, :importance, :confidence, :content_hash, :supersedes_id
                FROM memories WHERE id = :old_id
                RETURNING id
            """),
            {
                "new_id": new_id,
                "content": new_content,
                "embedding": _format_embedding(embedding),
                "tags": tags,
                "importance": importance,
                "confidence": confidence,
                "content_hash": content_hash,
                "supersedes_id": existing_id,
                "old_id": existing_id,
            }
        )
        
        # Create audit logs
        await self._create_audit_log(
            existing_id, AuditAction.UPDATE,
            diff={"before": {"content": existing["content"]}, "after": {"content": new_content}}
        )
        
        return {
            "action": "updated",
            "memory_id": str(new_id),
            "superseded_id": str(existing_id),
            "message": f"Memory updated (supersedes {existing_id})",
        }
    
    async def _create_audit_log(
        self,
        memory_id: uuid.UUID,
        action: AuditAction,
        actor_type: ActorType = ActorType.SYSTEM,
        diff: Optional[dict] = None,
    ):
        """Create an audit log entry."""
        await self.session.execute(
            text("""
                INSERT INTO memory_audit_logs (memory_id, action, actor_type, diff)
                VALUES (:memory_id, :action, :actor_type, :diff)
            """),
            {
                "memory_id": memory_id,
                "action": action.value,
                "actor_type": actor_type.value,
                "diff": _format_jsonb(diff),
            }
        )
    
    async def search_memories(
        self,
        user_id: uuid.UUID,
        query: Optional[str] = None,
        tags: Optional[list[str]] = None,
        memory_type: Optional[MemoryType] = None,
        scope: Scope = Scope.GLOBAL,
        agent_id: Optional[str] = None,
        include_global: bool = True,
        limit: int = 50,
    ) -> list[dict]:
        """Search memories with optional vector similarity."""
        # Set RLS context
        await self._apply_rls(user_id)
        
        conditions = ["valid_to IS NULL", "user_id = :user_id"]
        params = {"user_id": user_id, "limit": limit}
        
        # Scope filtering
        if scope == Scope.AGENT and agent_id:
            if include_global:
                conditions.append("(scope = 'global' OR (scope = 'agent' AND agent_id = :agent_id))")
            else:
                conditions.append("scope = 'agent' AND agent_id = :agent_id")
            params["agent_id"] = agent_id
        else:
            conditions.append("scope = 'global'")
        
        # Tag filtering
        if tags:
            conditions.append("tags @> :tags")
            params["tags"] = tags
        
        # Memory type filtering
        if memory_type:
            conditions.append("memory_type = :memory_type")
            params["memory_type"] = memory_type.value
        
        # Build query
        order_by = "created_at DESC"
        select_cols = "id, user_id, content, memory_type, tags, scope, agent_id, importance, confidence, created_at"
        
        # Vector similarity search if query provided
        if query:
            embedding = await generate_embedding(query)
            params["embedding"] = _format_embedding(embedding)
            select_cols += ", 1 - (embedding <=> CAST(:embedding AS vector)) as similarity"
            order_by = "embedding <=> CAST(:embedding AS vector)"
        
        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT {select_cols}
            FROM memories
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT :limit
        """
        
        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()
        
        now = datetime.now().astimezone()
        memories = []
        
        for row in rows:
            mem = {
                "id": str(row[0]),
                "user_id": str(row[1]),
                "content": row[2],
                "memory_type": row[3],
                "tags": row[4],
                "scope": row[5],
                "agent_id": row[6],
                "importance": row[7],
                "confidence": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
            }
            
            # Base score from similarity or default
            similarity = row[10] if (query and len(row) > 10) else 0.5
            mem["similarity"] = similarity
            
            # Ranking Factors
            # 1. Importance (1-5, normalized to 3)
            importance_weight = mem["importance"] / 3.0
            
            # 2. Confidence (0-1)
            confidence_weight = mem["confidence"]
            
            # 3. Recency Decay (Only for STATE and EPISODE)
            decay_weight = 1.0
            if mem["memory_type"] in [MemoryType.STATE.value, MemoryType.EPISODE.value]:
                if row[8]: # created_at
                    # Ensure both are offset-aware
                    created_at = row[8]
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=now.tzinfo)
                    
                    hours_old = (now - created_at).total_seconds() / 3600
                    # Decay formula: 1 / (1 + rate * hours)
                    # rate = 0.001 means ~50% score after 40 days
                    decay_weight = 1.0 / (1.0 + 0.001 * hours_old)
            
            # Final Rank Score
            # We call it 'score' to distinguish from raw similarity
            mem["score"] = similarity * importance_weight * confidence_weight * decay_weight
            
            memories.append(mem)
        
        # Re-sort by final score if it's a RAG query
        if query:
            memories.sort(key=lambda x: x["score"], reverse=True)
        
        return memories
    
    async def get_memory(self, memory_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[dict]:
        """Get a single memory by ID."""
        if user_id:
            await self._apply_rls(user_id)
            
        result = await self.session.execute(
            text("""
                SELECT id, user_id, content, memory_type, tags, scope, agent_id,
                       importance, confidence, source, created_at, updated_at
                FROM memories WHERE id = :id
            """),
            {"id": memory_id}
        )
        row = result.fetchone()
        if row:
            return {
                "id": str(row[0]),
                "user_id": str(row[1]),
                "content": row[2],
                "memory_type": row[3],
                "tags": row[4],
                "scope": row[5],
                "agent_id": row[6],
                "importance": row[7],
                "confidence": row[8],
                "source": row[9],
                "created_at": row[10].isoformat() if row[10] else None,
                "updated_at": row[11].isoformat() if row[11] else None,
            }
        return None
    
    async def update_memory(
        self,
        memory_id: uuid.UUID,
        user_id: uuid.UUID,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
        importance: Optional[int] = None,
        confidence: Optional[float] = None,
    ) -> Optional[dict]:
        """Update a memory's metadata."""
        # Set RLS context
        await self._apply_rls(user_id)
        
        # Get current state for audit
        current = await self.get_memory(memory_id)
        if not current:
            return None
        
        updates = []
        params = {"id": memory_id}
        diff_before = {}
        diff_after = {}
        
        if content is not None:
            updates.append("content = :content")
            params["content"] = content
            params["content_hash"] = compute_content_hash(content)
            updates.append("content_hash = :content_hash")
            # Regenerate embedding
            embedding = await generate_embedding(content)
            updates.append("embedding = CAST(:embedding AS vector)")
            params["embedding"] = _format_embedding(embedding)
            diff_before["content"] = current["content"]
            diff_after["content"] = content
        
        if tags is not None:
            updates.append("tags = :tags")
            params["tags"] = tags
            diff_before["tags"] = current["tags"]
            diff_after["tags"] = tags
        
        if importance is not None:
            updates.append("importance = :importance")
            params["importance"] = importance
            diff_before["importance"] = current["importance"]
            diff_after["importance"] = importance
        
        if confidence is not None:
            updates.append("confidence = :confidence")
            params["confidence"] = confidence
            diff_before["confidence"] = current["confidence"]
            diff_after["confidence"] = confidence
        
        if not updates:
            return current
        
        updates.append("updated_at = NOW()")
        
        await self.session.execute(
            text(f"UPDATE memories SET {', '.join(updates)} WHERE id = :id"),
            params
        )
        
        # Audit log
        await self._create_audit_log(
            memory_id, AuditAction.UPDATE,
            actor_type=ActorType.USER,
            diff={"before": diff_before, "after": diff_after}
        )
        
        return await self.get_memory(memory_id)
    
    async def delete_memory(self, memory_id: uuid.UUID, user_id: uuid.UUID, hard_delete: bool = False) -> bool:
        """Delete a memory (soft delete by default)."""
        # Set RLS context
        await self._apply_rls(user_id)
        
        if hard_delete:
            result = await self.session.execute(
                text("DELETE FROM memories WHERE id = :id RETURNING id"),
                {"id": memory_id}
            )
        else:
            result = await self.session.execute(
                text("""
                    UPDATE memories SET valid_to = NOW(), updated_at = NOW()
                    WHERE id = :id AND valid_to IS NULL
                    RETURNING id
                """),
                {"id": memory_id}
            )
        
        row = result.fetchone()
        if row:
            await self._create_audit_log(
                memory_id, AuditAction.DELETE,
                actor_type=ActorType.USER
            )
            return True
        return False
