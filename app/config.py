"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str = "postgresql+asyncpg://cortex:cortex_password@localhost:5432/cortex_db"
    
    # Google AI (Gemini)
    google_api_key: str = ""
    
    # API Settings
    api_key: str = ""  # X-API-KEY for auth (optional for dev)
    debug: bool = True
    
    # Embedding Settings
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768
    
    # AI Analysis Settings
    llm_model: str = "models/gemini-2.0-flash-lite"
    
    # Vector Search Settings
    similarity_threshold: float = 0.95
    default_search_limit: int = 50
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
