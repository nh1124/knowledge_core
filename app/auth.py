import hmac
import hashlib
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from passlib.context import CryptContext

from app.services.database import get_db
from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
logger = get_logger("auth")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)

class Identity(BaseModel):
    user_id: uuid.UUID
    client_id: Optional[str] = None
    scopes: List[str] = []
    auth_method: str # local, api_key, external, dev_fallback
    issuer: Optional[str] = None
    audience: Optional[str] = None
    warnings: List[str] = []
    is_admin: bool = False
    gemini_api_key: Optional[str] = None

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def hash_api_key(api_key: str) -> str:
    """Hash an API key using HMAC-SHA256 with a server-side pepper."""
    pepper = settings.kc_api_key_pepper or "default_dev_pepper_change_me_in_prod"
    return hmac.new(
        pepper.encode(),
        api_key.encode(),
        hashlib.sha256
    ).hexdigest()


def _get_encryption_key() -> bytes:
    """Derive a Fernet-compatible key from server secret."""
    import base64
    secret = (settings.kc_secret_key or settings.secret_key).encode()
    # Use first 32 bytes of SHA256 hash, then base64 encode for Fernet
    key_bytes = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string for storage."""
    from cryptography.fernet import Fernet
    if not plaintext:
        return ""
    f = Fernet(_get_encryption_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a stored secret string."""
    from cryptography.fernet import Fernet
    if not ciphertext:
        return ""
    try:
        f = Fernet(_get_encryption_key())
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.warning(f"Failed to decrypt secret: {e}")
        return ""

async def get_identity_from_jwt(token: str) -> dict:
    try:
        secret = settings.kc_secret_key or settings.secret_key
        payload = jwt.decode(
            token, 
            secret, 
            algorithms=[settings.algorithm],
            options={"verify_aud": False} # We check it manually in dependencies if needed
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT Verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def resolve_identity(
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    token: Optional[str] = Depends(oauth2_scheme)
) -> Identity:
    warnings = []
    
    # 1. JWT Auth (Primary for UI/Users)
    if token:
        payload = await get_identity_from_jwt(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")
        
        issuer = payload.get("iss")
        # Scenario A: Local JWT - fetch gemini_api_key
        if issuer == "kc":
             result = await db.execute(
                 text("SELECT gemini_api_key FROM users WHERE user_id = :id"),
                 {"id": user_id_str}
             )
             user_row = result.fetchone()
             # Decrypt the stored key
             decrypted_key = decrypt_secret(user_row[0]) if user_row and user_row[0] else None
             return Identity(
                user_id=uuid.UUID(user_id_str),
                auth_method="local",
                issuer=issuer,
                audience=payload.get("aud"),
                scopes=payload.get("scopes", []),
                is_admin=payload.get("is_admin", False),
                warnings=warnings,
                gemini_api_key=decrypted_key
            )
        
        # Scenario B: External JWT
        result = await db.execute(
            text("""
                SELECT ei.user_id, u.gemini_api_key 
                FROM external_identities ei
                JOIN users u ON ei.user_id = u.user_id
                WHERE ei.issuer = :i AND ei.subject = :s
            """),
            {"i": issuer, "s": user_id_str}
        )
        row = result.fetchone()
        if row:
            decrypted_key = decrypt_secret(row[1]) if row[1] else None
            return Identity(
                user_id=row[0],
                auth_method="external",
                issuer=issuer,
                audience=payload.get("aud"),
                scopes=payload.get("scopes", []),
                warnings=warnings,
                gemini_api_key=decrypted_key
            )

        return Identity(
            user_id=uuid.UUID(user_id_str),
            auth_method="local",
            scopes=payload.get("scopes", []),
            is_admin=payload.get("is_admin", False),
            warnings=warnings
        )

    # 2. API Key Auth (Primary for Automation/M2M)
    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        
        # Check DB for API Key
        result = await db.execute(
            text("""
                SELECT a.user_id, a.client_id, a.scopes, a.is_active, a.is_admin, u.gemini_api_key
                FROM api_keys a
                JOIN users u ON a.user_id = u.user_id
                WHERE a.key_hash = :h AND a.is_active = TRUE
            """),
            {"h": key_hash}
        )
        row = result.fetchone()
        
        if row:
            user_id, client_id, scopes, is_active, is_admin, encrypted_gemini_key = row
            decrypted_gemini_key = decrypt_secret(encrypted_gemini_key) if encrypted_gemini_key else None
            
            # Update last_used_at
            await db.execute(
                text("UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = :h"),
                {"h": key_hash}
            )
            
            return Identity(
                user_id=user_id,
                client_id=client_id,
                scopes=scopes or [],
                auth_method="api_key",
                is_admin=is_admin,
                warnings=warnings,
                gemini_api_key=decrypted_gemini_key
            )
        
        # Legacy Fallback (if enabled)
        if settings.kc_enable_legacy_api_key and settings.api_key:
            if hmac.compare_digest(x_api_key, settings.api_key):
                return Identity(
                    user_id=uuid.UUID(settings.kc_default_user_id),
                    client_id="legacy_client",
                    scopes=["ingest", "context", "memories:read", "memories:write", "dump"],
                    auth_method="api_key",
                    is_admin=True,
                    warnings=["legacy_api_key_used"]
                )

    # 3. Dev Fallback
    if settings.skip_auth or (not settings.kc_require_api_key and settings.debug):
        return Identity(
            user_id=uuid.UUID(settings.kc_default_user_id),
            auth_method="dev_fallback",
            scopes=["ingest", "context", "memories:read", "memories:write", "dump"],
            is_admin=True,
            warnings=["Authenticated via Dev Fallback"]
        )

    # 4. Final failure
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid authentication",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def require_local_user(identity: Identity = Depends(resolve_identity)) -> Identity:
    """Accept ONLY local KC session or dev fallback."""
    if identity.auth_method == "dev_fallback":
        return identity
    if identity.auth_method != "local":
        raise HTTPException(status_code=401, detail="Local session required")
    return identity

async def require_user_identity(identity: Identity = Depends(resolve_identity)) -> Identity:
    """Accept local or external identities (human sessions or linked accounts). Reject API Keys."""
    if identity.auth_method == "dev_fallback":
        return identity
    if identity.auth_method not in ["local", "external"]:
        raise HTTPException(status_code=401, detail="User session required")
    return identity

async def require_client_api_key(identity: Identity = Depends(resolve_identity)) -> Identity:
    """Accept ONLY API Key or dev fallback."""
    if identity.auth_method == "dev_fallback":
        return identity
    if identity.auth_method != "api_key":
        raise HTTPException(status_code=403, detail="API Key required")
    return identity

async def require_external_identity(
    x_external_jwt: str = Header(..., alias="X-EXTERNAL-JWT")
) -> dict:
    """Verifies external JWT and returns payload."""
    # We use the same get_identity_from_jwt logic but it might have different secret/algorithm in real world.
    # For simplicity of "parity", we assume the same secret or we can just decode without verify if it's meant to be verified later.
    # LBS uses get_identity_from_jwt(x_external_jwt).
    return await get_identity_from_jwt(x_external_jwt)

def create_access_token(
    user_id: uuid.UUID, 
    is_admin: bool = False, 
    scopes: List[str] = None,
    issuer: str = "kc",
    audience: str = "kc-ui"
):
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "iss": issuer,
        "aud": audience,
        "is_admin": is_admin,
        "scopes": scopes or []
    }
    
    secret = settings.kc_secret_key or settings.secret_key
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=settings.algorithm)
    return encoded_jwt
