"""Antigravity Cortex - Knowledge Core API.

A knowledge management microservice for storing and retrieving user memories
with AI-powered analysis, vector search, and context synthesis.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import os
from sqlalchemy import text
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.routers import ingest, memories, context
from app.dependencies import verify_api_key
from app.logging_config import setup_logging

settings = get_settings()
logger = setup_logging()

# Static files directory
STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Antigravity Cortex starting...")
    logger.info(f"Static files: {STATIC_DIR}")
    yield
    # Shutdown
    logger.info("Antigravity Cortex shutting down...")


app = FastAPI(
    title="Antigravity Cortex",
    description="Knowledge Core - AI-powered memory management for personalized context",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Unified error handler
@app.exception_handler(Exception)
async def unified_exception_handler(request: Request, exc: Exception):
    """Global exception handler to return unified error format."""
    status_code = 500
    error_code = "INTERNAL_ERROR"
    message = str(exc)
    details = {}

    if isinstance(exc, StarletteHTTPException):
        status_code = exc.status_code
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=status_code, content=exc.detail)
        message = str(exc.detail)
        error_code = "HTTP_EXCEPTION"
    elif isinstance(exc, RequestValidationError):
        status_code = 422
        error_code = "VALIDATION_ERROR"
        message = "Validation error"
        details = {"errors": exc.errors()}

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": message,
                "details": details
            }
        }
    )


# Include routers with security dependency
api_dependencies = [Depends(verify_api_key)] if not settings.skip_auth else []
app.include_router(ingest.router, dependencies=api_dependencies)
app.include_router(memories.router, dependencies=api_dependencies)
app.include_router(context.router, dependencies=api_dependencies)


# Memory Gardener UI
@app.get("/ui")
@app.get("/ui/")
async def serve_ui():
    """Serve Memory Gardener UI."""
    return FileResponse(STATIC_DIR / "index.html")


# Mount static files (for any additional assets)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Antigravity Cortex",
        "version": "1.0.0",
        "status": "operational",
        "ui": "/ui",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    from app.services.database import SessionLocal
    from app.services.embedding import generate_embedding
    
    db_status = "connected"
    ai_status = "ready"
    errors = []
    
    # 1. Check Database
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "disconnected"
        errors.append(f"Database: {str(e)}")
        
    # 2. Check AI Engine (Embedding)
    try:
        # Just a small test embedding
        await generate_embedding("health check")
    except Exception as e:
        ai_status = "error"
        errors.append(f"AI Engine: {str(e)}")
        
    return {
        "status": "healthy" if db_status == "connected" and ai_status == "ready" else "degraded",
        "database": db_status,
        "ai_engine": ai_status,
        "errors": errors if errors else None
    }

