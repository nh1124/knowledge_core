"""Embedding service using Google Gemini."""
import hashlib
from typing import Optional

import google.generativeai as genai

from app.config import get_settings

settings = get_settings()

# Configure Gemini
genai.configure(api_key=settings.google_api_key)


async def generate_embedding(text: str, api_key: Optional[str] = None) -> list[float]:
    """Generate embedding vector for text using Gemini.
    
    Args:
        text: Text to embed
        api_key: Optional per-user API key
        
    Returns:
        768-dimensional embedding vector
    """
    effective_api_key = api_key or settings.google_api_key
    if not effective_api_key:
        raise ValueError("No Gemini API key available for embedding")
        
    genai.configure(api_key=effective_api_key)
    
    result = genai.embed_content(
        model=settings.embedding_model,
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]


async def generate_embeddings(texts: list[str], api_key: Optional[str] = None) -> list[list[float]]:
    """Generate embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
        api_key: Optional per-user API key
        
    Returns:
        List of 768-dimensional embedding vectors
    """
    embeddings = []
    for text in texts:
        embedding = await generate_embedding(text, api_key=api_key)
        embeddings.append(embedding)
    return embeddings


def compute_content_hash(content: str) -> str:
    """Compute hash of normalized content for deduplication.
    
    Args:
        content: Memory content
        
    Returns:
        SHA-256 hash of normalized content
    """
    # Normalize: lowercase, strip whitespace, remove extra spaces
    normalized = " ".join(content.lower().strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()
