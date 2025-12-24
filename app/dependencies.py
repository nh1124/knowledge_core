"""API Dependencies - Security and shared resources."""
import uuid
from typing import Optional, List
from contextvars import ContextVar
from fastapi import Depends, HTTPException, status, Query

from app.auth import Identity, resolve_identity
from app.models.enums import Scope

# Context var to store warnings for the current request
request_warnings: ContextVar[List[str]] = ContextVar("request_warnings", default=[])

async def verify_api_key(identity: Identity = Depends(resolve_identity)) -> Identity:
    """Compatibility layer for existing code: verify identity and return it."""
    if identity.warnings:
        warnings = request_warnings.get()
        for w in identity.warnings:
            if w not in warnings:
                warnings.append(w)
        request_warnings.set(warnings)
    return identity

def require_scope(required_scope: str):
    """Dependency factory to enforce required scopes."""
    async def scope_checker(identity: Identity = Depends(resolve_identity)):
        if identity.is_admin:
            return identity
            
        if required_scope not in identity.scopes:
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

async def require_admin(identity: Identity = Depends(resolve_identity)):
    """Accept ONLY admins."""
    if not identity.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return identity

async def resolve_user_id(
    identity: Identity = Depends(resolve_identity),
    user_id: Optional[uuid.UUID] = Query(None)
) -> uuid.UUID:
    """Resolve user_id. 
    If user_id is provided in query, it MUST match the identity's user_id UNLESS identity is admin.
    """
    if user_id:
        if not identity.is_admin and identity.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot access data for another user"
            )
        return user_id
    
    return identity.user_id

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
