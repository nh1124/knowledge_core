import secrets
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.services.database import get_db
from app.services.auth_service import hash_api_key, APIKeyIdentity
from app.dependencies import resolve_api_key_identity, require_scope
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])

class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., example="My App Key")
    client_id: str = Field(..., example="my_mobile_app")
    scopes: List[str] = Field(default=["memories:read", "context"], example=["memories:read", "context"])
    is_admin: bool = False

class APIKeyResponse(BaseModel):
    id: uuid.UUID
    client_id: str
    name: Optional[str]
    scopes: List[str]
    is_active: bool
    is_admin: bool
    created_at: str
    last_used_at: Optional[str]

class APIKeyNewResponse(BaseModel):
    status: str
    api_key: str
    details: APIKeyResponse

@router.post("/keys", response_model=APIKeyNewResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    identity: APIKeyIdentity = Depends(require_scope("admin"))
):
    """Generate a new API key. Requires admin privileges."""
    # Generate plaintext key
    raw_key = f"kc_{secrets.token_urlsafe(32)}"
    hashed = hash_api_key(raw_key)
    
    # Insert into DB
    key_id = uuid.uuid4()
    query = text("""
        INSERT INTO api_keys (id, key_hash, client_id, scopes, is_admin, name)
        VALUES (:id, :hash, :client_id, :scopes, :is_admin, :name)
        RETURNING id, client_id, name, scopes, is_active, is_admin, created_at
    """)
    
    result = await db.execute(query, {
        "id": key_id,
        "hash": hashed,
        "client_id": request.client_id,
        "scopes": request.scopes,
        "is_admin": request.is_admin,
        "name": request.name
    })
    
    row = result.fetchone()
    await db.commit()
    
    return APIKeyNewResponse(
        status="success",
        api_key=raw_key,
        details=APIKeyResponse(
            id=row[0],
            client_id=row[1],
            name=row[2],
            scopes=row[3],
            is_active=row[4],
            is_admin=row[5],
            created_at=row[6].isoformat(),
            last_used_at=None
        )
    )

@router.get("/keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    identity: APIKeyIdentity = Depends(require_scope("admin"))
):
    """List all API keys. Requires admin privileges."""
    query = text("SELECT id, client_id, name, scopes, is_active, is_admin, created_at, last_used_at FROM api_keys ORDER BY created_at DESC")
    result = await db.execute(query)
    rows = result.fetchall()
    
    return [
        APIKeyResponse(
            id=r[0],
            client_id=r[1],
            name=r[2],
            scopes=r[3],
            is_active=r[4],
            is_admin=r[5],
            created_at=r[6].isoformat(),
            last_used_at=r[7].isoformat() if r[7] else None
        ) for r in rows
    ]

@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: APIKeyIdentity = Depends(require_scope("admin"))
):
    """Revoke (deactivate) an API key."""
    query = text("UPDATE api_keys SET is_active = FALSE, revoked_at = NOW() WHERE id = :id")
    await db.execute(query, {"id": key_id})
    await db.commit()
    return {"status": "revoked"}
