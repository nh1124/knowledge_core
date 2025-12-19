"""API Dependencies - Security and shared resources."""
import uuid
from typing import Optional, List
from contextvars import ContextVar
from fastapi import Header, HTTPException, status, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.logging_config import get_logger
from app.models.enums import Scope
from app.services.database import get_db
from app.services.auth_service import APIKeyManager, APIKeyIdentity

settings = get_settings()
logger = get_logger("dependencies")

# Context var to store warnings for the current request
request_warnings: ContextVar[List[str]] = ContextVar("request_warnings", default=[])

async def resolve_api_key_identity(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> APIKeyIdentity:
    """Resolve API key to client identity with DB lookup and legacy fallback."""
    if settings.skip_auth:
        return APIKeyIdentity(
            client_id="skipped_auth_dev",
            scopes=["ingest", "context", "memories:read", "memories:write", "dump"],
            is_admin=True
        )
        
    auth_manager = APIKeyManager(db)
    identity = await auth_manager.resolve_identity(x_api_key)
    
    if not identity:
        logger.warning(f"Unauthorized access attempt with invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API Key"
                }
            }
        )
        
    if identity.warning:
        logger.warning(f"Legacy API key used by client: {identity.client_id}")
        # Add warning to context
        warnings = request_warnings.get()
        if identity.warning not in warnings:
            warnings.append(identity.warning)
            request_warnings.set(warnings)
            
    return identity

def require_scope(required_scope: str):
    """Dependency factory to enforce required scopes."""
    async def scope_checker(identity: APIKeyIdentity = Depends(resolve_api_key_identity)):
        if identity.is_admin:
            return identity
            
        if required_scope not in identity.scopes:
            logger.error(f"Client {identity.client_id} lacks required scope: {required_scope}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Missing required scope: {required_scope}"
                    }
                }
            )
        return identity
    return scope_checker

async def verify_api_key(identity: APIKeyIdentity = Depends(resolve_api_key_identity)):
    """Legacy compatibility: verify key and return identity."""
    return identity

async def resolve_user_id(user_id: Optional[uuid.UUID] = Query(None)) -> uuid.UUID:
    """Resolve user_id from query parameter or fallback to default."""
    if user_id:
        return user_id
    
    if settings.kc_require_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": "user_id is required"
                }
            }
        )
    
    # Fallback mode
    fallback_id = uuid.UUID(settings.kc_default_user_id)
    logger.warning(f"user_id missing, using fallback: {fallback_id}")
    
    # Add warning to context
    warnings = request_warnings.get()
    if "user_id_missing_fallback_used" not in warnings:
        warnings.append("user_id_missing_fallback_used")
        request_warnings.set(warnings)
        
    return fallback_id

async def resolve_scope_and_agent(
    scope: Scope = Query(Scope.GLOBAL),
    agent_id: Optional[str] = Query(None)
) -> tuple[Scope, Optional[str]]:
    """Validate scope and agent_id combination."""
    if scope == Scope.AGENT and not agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_ARGUMENT",
                    "message": "agent_id is required when scope=AGENT"
                }
            }
        )
    return scope, agent_id
