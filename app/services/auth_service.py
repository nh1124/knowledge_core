"""Auth Service - Identity verification and API key management."""
import hmac
import hashlib
import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()

class APIKeyIdentity(BaseModel):
    """Resolved identity from an API key."""
    client_id: str
    scopes: List[str]
    is_admin: bool = False
    warning: Optional[str] = None

def hash_api_key(api_key: str) -> str:
    """Hash an API key using HMAC-SHA256 with a server-side pepper."""
    if not settings.kc_api_key_pepper:
        # In development, we might allow empty pepper but it should be warned
        pepper = "default_dev_pepper_change_me_in_prod"
    else:
        pepper = settings.kc_api_key_pepper
        
    return hmac.new(
        pepper.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def compare_hashes(h1: str, h2: str) -> bool:
    """Constant-time comparison of two hashes to prevent timing attacks."""
    return hmac.compare_digest(h1, h2)

class APIKeyManager:
    """Manager for API key lookups and maintenance."""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_identity(self, api_key: str) -> Optional[APIKeyIdentity]:
        """Resolve an API key to a client identity.
        
        Checks DB first, then falls back to legacy .env key if enabled.
        """
        # 1. Check DB
        key_hash = hash_api_key(api_key)
        
        result = await self.session.execute(
            text("""
                SELECT client_id, scopes, is_admin, is_active
                FROM api_keys
                WHERE key_hash = :h AND is_active = TRUE
            """),
            {"h": key_hash}
        )
        row = result.fetchone()
        
        if row:
            # Update last_used_at (background/fire-and-forget ideally, but async here is fine)
            await self.session.execute(
                text("UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = :h"),
                {"h": key_hash}
            )
            return APIKeyIdentity(
                client_id=row.client_id,
                scopes=row.scopes,
                is_admin=row.is_admin
            )
            
        # 2. Check Legacy Fallback
        if settings.kc_enable_legacy_api_key and settings.api_key:
            if hmac.compare_digest(api_key, settings.api_key):
                return APIKeyIdentity(
                    client_id="legacy_client",
                    scopes=["ingest", "context", "memories:read", "memories:write", "dump"], # Full access for legacy
                    is_admin=True,
                    warning="legacy_api_key_used"
                )
        
        return None
