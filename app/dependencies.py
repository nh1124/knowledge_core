"""API Dependencies - Security and shared resources."""
import uuid
from typing import Optional, List
from contextvars import ContextVar
from fastapi import Header, HTTPException, status, Query
from app.config import get_settings
from app.logging_config import get_logger
from app.models.enums import Scope

settings = get_settings()
logger = get_logger("dependencies")

# Context var to store warnings for the current request
request_warnings: ContextVar[List[str]] = ContextVar("request_warnings", default=[])

async def verify_api_key(x_api_key: str = Header(...)):
    """Verify the X-API-KEY header."""
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API Key"
                }
            }
        )
    return x_api_key

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
