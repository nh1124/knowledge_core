"""Antigravity Cortex - Knowledge Core API.

A knowledge management microservice for storing and retrieving user memories
with AI-powered analysis, vector search, and context synthesis.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import ingest, memories, context

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("🧠 Antigravity Cortex starting...")
    yield
    # Shutdown
    print("🧠 Antigravity Cortex shutting down...")


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


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc) if settings.debug else "Internal server error",
            }
        },
    )


# Include routers
app.include_router(ingest.router)
app.include_router(memories.router)
app.include_router(context.router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Antigravity Cortex",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: actual check
        "ai_engine": "ready",     # TODO: actual check
    }
