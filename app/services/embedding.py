"""Embedding service using Google Gemini."""
import hashlib
from typing import Optional

import google.generativeai as genai

from app.config import get_settings

settings = get_settings()

# Configure Gemini
genai.configure(api_key=settings.google_api_key)


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text using Gemini.
    
    Args:
        text: Text to embed
        
    Returns:
        768-dimensional embedding vector
    """
    result = genai.embed_content(
        model=settings.embedding_model,
        content=text,
        task_type="retrieval_document",
    )
    return result["embedding"]


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of 768-dimensional embedding vectors
    """
    embeddings = []
    for text in texts:
        embedding = await generate_embedding(text)
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
