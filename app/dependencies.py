"""API Dependencies - Security and shared resources."""
from fastapi import Header, HTTPException, status
from app.config import get_settings

settings = get_settings()

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
