"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server
    host: str = "0.0.0.0"
    backend_port: int = 8000
    kc_host_port: int = 8200
    
    # Database
    database_url: str = "postgresql+asyncpg://cortex:cortex_password@localhost:5432/cortex_db"
    
    # Auth
    skip_auth: bool = False
    debug: bool = True
    
    # API Authorization Settings
    kc_api_key_pepper: str = ""  # HMAC secret - REQUIRED in production
    kc_secret_key: str = ""      # Same as secret_key, but using kc_ prefix for consistency
    kc_enable_legacy_api_key: bool = True  # Fallback to .env API_KEY with warning
    kc_require_api_key: bool = True  # Enforce key check even if legacy is disabled
    
    # Embedding Settings
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768
    
    # API Security
    api_key: str = "cortex_secret_key_2025"  # Default for dev
    secret_key: str = "cortex_internal_secret_key_change_me_in_prod"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    
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
        extra = "ignore"  # Prevent crashes if extra env vars are present


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
