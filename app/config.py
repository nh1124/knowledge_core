"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8200
    
    # Database
    database_url: str = "postgresql+asyncpg://cortex:cortex_password@localhost:5432/cortex_db"
    
    # Google AI (Gemini)
    google_api_key: str = ""
    
    api_key: str = ""  # X-API-KEY for auth (optional for dev)
    skip_auth: bool = False
    debug: bool = True
    
    # Embedding Settings
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768
    
    # API Security
    api_key: str = "cortex_secret_key_2025"  # Default for dev
    
    # AI Analysis Settings
    llm_model: str = "models/gemini-2.5-flash-lite"
    
    # Vector Search Settings
    similarity_threshold: float = 0.95
    default_search_limit: int = 50
    
    # Logging Settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: str = "logs/app.log"
    
    # User ID Resolution
    kc_require_user_id: bool = False
    kc_default_user_id: str = "00000000-0000-0000-0000-000000000001"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
