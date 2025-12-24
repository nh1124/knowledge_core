import secrets
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from pydantic import BaseModel, Field

from app.services.database import get_db
from app.auth import (
    hash_api_key, 
    Identity, 
    create_access_token, 
    verify_password, 
    get_password_hash,
    resolve_identity,
    require_local_user,
    require_client_api_key,
    require_external_identity,
    require_user_identity,
    encrypt_secret
)
from app.dependencies import require_admin
from app.logging_config import get_logger

logger = get_logger("auth_router")

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])

# --- Auth Models ---

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    is_admin: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID

class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    name: Optional[str]
    is_admin: bool
    is_active: bool
    auth_method: Optional[str] = None
    has_gemini_key: bool = False  # Indicates if user has configured a key, but never expose value

# --- API Key Models ---

class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., example="My App Key")
    client_id: Optional[str] = Field(None, example="my_mobile_app")
    scopes: List[str] = Field(default=["memories:read", "context"], example=["memories:read", "context"])
    is_admin: bool = False

class APIKeyResponse(BaseModel):
    id: uuid.UUID
    client_id: Optional[str] = None
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

# --- Auth Models ---

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class SystemConfigResponse(BaseModel):
    google_api_key: str
    log_level: str
    debug: bool

class SystemConfigRequest(BaseModel):
    google_api_key: Optional[str] = None
    log_level: Optional[str] = None
    debug: Optional[bool] = None

class UserSettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None

# --- Endpoints ---

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT."""
    result = await db.execute(
        text("SELECT user_id, password_hash, is_admin, is_active FROM users WHERE email = :e"),
        {"e": request.email}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    user_id, hashed_pass, is_admin, is_active = row
    
    if not is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")
        
    if not verify_password(request.password, hashed_pass):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    # Get user scopes (placeholder or from DB)
    scopes = ["memories:read", "memories:write", "context", "ingest", "dump"]
    
    token = create_access_token(user_id=user_id, is_admin=is_admin, scopes=scopes)
    
    return TokenResponse(access_token=token, user_id=user_id)

@router.post("/register", response_model=dict)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user. For dev/setup purposes."""
    # Check if user exists
    existing = await db.execute(text("SELECT 1 FROM users WHERE email = :e"), {"e": request.email})
    if existing.fetchone():
        raise HTTPException(status_code=400, detail="User already exists")
        
    hashed_pass = get_password_hash(request.password)
    user_id = uuid.uuid4()
    
    await db.execute(
        text("INSERT INTO users (user_id, email, password_hash, name, is_admin) VALUES (:id, :e, :h, :n, :a)"),
        {"id": user_id, "e": request.email, "h": hashed_pass, "n": request.name, "a": request.is_admin}
    )
    await db.commit()
    return {"status": "User created", "user_id": user_id}

@router.post("/keys", response_model=APIKeyNewResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(resolve_identity)
):
    """Generate a new API key. Linked to the current user."""
    # Generate plaintext key
    raw_key = f"kc_{secrets.token_urlsafe(32)}"
    hashed = hash_api_key(raw_key)
    
    # Insert into DB
    key_id = uuid.uuid4()
    query = text("""
        INSERT INTO api_keys (id, key_hash, client_id, scopes, is_admin, name, user_id)
        VALUES (:id, :hash, :client_id, :scopes, :is_admin, :name, :user_id)
        RETURNING id, client_id, name, scopes, is_active, is_admin, created_at
    """)
    
    result = await db.execute(query, {
        "id": key_id,
        "hash": hashed,
        "client_id": request.client_id,
        "scopes": request.scopes,
        "is_admin": request.is_admin,
        "name": request.name,
        "user_id": identity.user_id
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
    identity: Identity = Depends(resolve_identity)
):
    """List API keys for the current user."""
    query = text("""
        SELECT id, client_id, name, scopes, is_active, is_admin, created_at, last_used_at 
        FROM api_keys 
        WHERE user_id = :uid 
        ORDER BY created_at DESC
    """)
    result = await db.execute(query, {"uid": identity.user_id})
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
    identity: Identity = Depends(resolve_identity)
):
    """Revoke (deactivate) an API key."""
    # Ensure user owns the key or is admin
    check = await db.execute(text("SELECT user_id FROM api_keys WHERE id = :id"), {"id": key_id})
    row = check.fetchone()
    if not row:
         raise HTTPException(status_code=404, detail="Key not found")
         
    if not identity.is_admin and row[0] != identity.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    query = text("UPDATE api_keys SET is_active = FALSE, revoked_at = NOW() WHERE id = :id")
    await db.execute(query, {"id": key_id})
    await db.commit()
    return {"status": "revoked"}

# --- Missing Endpoints ---

@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(require_user_identity)
):
    """Return current user profile (requires local Bearer token)."""
    result = await db.execute(
        text("SELECT user_id, email, name, is_admin, is_active, gemini_api_key FROM users WHERE user_id = :id"),
        {"id": identity.user_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        user_id=row[0],
        email=row[1],
        name=row[2],
        is_admin=row[3],
        is_active=row[4],
        auth_method=identity.auth_method,
        has_gemini_key=bool(row[5]) if len(row) > 5 else False
    )

@router.get("/keys/me", response_model=APIKeyResponse)
async def get_my_key_info(
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(require_client_api_key)
):
    """Return current API key profile (requires X-API-KEY)."""
    # Note: identity.client_id should be set for api_key auth
    result = await db.execute(
        text("""
            SELECT id, client_id, name, scopes, is_active, is_admin, created_at, last_used_at
            FROM api_keys
            WHERE user_id = :uid AND client_id = :cid AND is_active = TRUE
        """),
        {"uid": identity.user_id, "cid": identity.client_id}
    )
    row = result.fetchone()
    if not row:
         raise HTTPException(status_code=404, detail="API Key record not found")
         
    return APIKeyResponse(
        id=row[0],
        client_id=row[1],
        name=row[2],
        scopes=row[3],
        is_active=row[4],
        is_admin=row[5],
        created_at=row[6].isoformat(),
        last_used_at=row[7].isoformat() if row[7] else None
    )

@router.post("/link/confirm")
async def confirm_link_external(
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(require_local_user),
    external_payload: dict = Depends(require_external_identity)
):
    """Link a verified external system JWT to the current local account."""
    issuer = external_payload.get("iss")
    subject = external_payload.get("sub")
    
    if not issuer or not subject:
        raise HTTPException(status_code=400, detail="External JWT missing iss or sub")

    # Check if already linked
    check = await db.execute(
        text("SELECT user_id FROM external_identities WHERE issuer = :i AND subject = :s"),
        {"i": issuer, "s": subject}
    )
    existing = check.fetchone()
    
    if existing:
        if existing[0] == identity.user_id:
            return {"message": "Already linked", "linked": True}
        else:
            raise HTTPException(status_code=409, detail="External identity already linked to another account")

    # Create link
    await db.execute(
        text("INSERT INTO external_identities (user_id, issuer, subject) VALUES (:uid, :i, :s)"),
        {"uid": identity.user_id, "i": issuer, "s": subject}
    )
    await db.commit()
    
    return {"message": "Linked successfully", "linked": True, "issuer": issuer, "subject": subject}

@router.get("/debug/triggers")
async def get_triggers(db: AsyncSession = Depends(get_db)):
    """Debug endpoint to list all triggers in the DB."""
    query = text("""
        SELECT trg.tgname AS trigger_name,
               reltbl.relname AS table_name,
               proname.proname AS function_name
        FROM pg_trigger trg
        JOIN pg_class reltbl ON reltbl.oid = trg.tgrelid
        JOIN pg_proc proname ON proname.oid = trg.tgfoid
        WHERE reltbl.relkind = 'r' 
        AND reltbl.relname NOT LIKE 'pg_%'
        AND reltbl.relname NOT LIKE 'sql_%'
    """)
    result = await db.execute(query)
    rows = result.fetchall()
    return [{"trigger_name": r[0], "table_name": r[1], "function_name": r[2]} for r in rows]

@router.post("/password/change")
async def change_password(
    request: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(require_local_user)
):
    """Change the current user's password."""
    # Fetch user
    result = await db.execute(
        text("SELECT password_hash FROM users WHERE user_id = :id"),
        {"id": identity.user_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_hash = row[0]
    if not verify_password(request.current_password, current_hash):
        raise HTTPException(status_code=401, detail="Incorrect current password")
    
    # Hash new password
    new_hash = get_password_hash(request.new_password)
    await db.execute(
        text("UPDATE users SET password_hash = :h WHERE user_id = :id"),
        {"h": new_hash, "id": identity.user_id}
    )
    await db.commit()
    return {"message": "Password changed successfully"}

@router.get("/config", response_model=SystemConfigResponse)
async def get_system_config(identity: Identity = Depends(require_admin)):
    """Fetch sensitive system configuration (Admin only)."""
    s = get_settings()
    return SystemConfigResponse(
        google_api_key=s.google_api_key,
        log_level=s.log_level,
        debug=s.debug
    )

@router.post("/config")
async def update_system_config(
    request: SystemConfigRequest,
    identity: Identity = Depends(require_admin)
):
    """Update system configuration (Admin only). Modifies .env for persistence."""
    env_path = ".env"
    from app.config import get_settings
    import os
    
    # This is a bit hacky but works for simple .env updates without external libs
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        updates = {}
        if request.google_api_key is not None: updates["GOOGLE_API_KEY"] = request.google_api_key
        if request.log_level is not None: updates["LOG_LEVEL"] = request.log_level
        if request.debug is not None: updates["DEBUG"] = str(request.debug)

        new_lines = []
        applied_keys = set()
        for line in lines:
            found = False
            for key, val in updates.items():
                if line.strip().startswith(f"{key}="):
                    new_lines.append(f"{key}={val}\n")
                    applied_keys.add(key)
                    found = True
                    break
            if not found:
                new_lines.append(line)
        
        # Add new keys if not present
        for key, val in updates.items():
            if key not in applied_keys:
                new_lines.append(f"{key}={val}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        return {"status": "success", "message": "Config updated. Server may reload."}
    except Exception as e:
        logger.error(f"Failed to update .env: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/delete-account")
async def delete_my_account(
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(require_local_user)
):
    """Delete the current user account and all associated data."""
    # Manually delete child records to avoid problematic cascading triggers
    await db.execute(text('DELETE FROM "external_identities" WHERE "user_id" = :uid'), {"uid": identity.user_id})
    await db.execute(text('DELETE FROM "api_keys" WHERE "user_id" = :uid'), {"uid": identity.user_id})
    await db.execute(text('DELETE FROM "memories" WHERE "user_id" = :uid'), {"uid": identity.user_id})
    
    # Finally delete user
    await db.execute(text('DELETE FROM "users" WHERE "user_id" = :uid'), {"uid": identity.user_id})
    await db.commit()
    
    logger.info(f"Account and all data deleted for user: {identity.user_id}")
    return {"status": "deleted", "user_id": identity.user_id}

@router.patch("/settings")
async def update_user_settings(
    request: UserSettingsRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(require_local_user)
):
    """Update per-user settings (Gemini API key)."""
    if request.gemini_api_key is not None:
        # Encrypt the key before storing
        encrypted_key = encrypt_secret(request.gemini_api_key) if request.gemini_api_key else ""
        await db.execute(
            text("UPDATE users SET gemini_api_key = :key WHERE user_id = :id"),
            {"key": encrypted_key, "id": identity.user_id}
        )
        await db.commit()
    return {"status": "success", "message": "Settings updated"}
