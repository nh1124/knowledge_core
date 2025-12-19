import logging
import sys
from pathlib import Path
from app.config import get_settings

def setup_logging():
    """Configure application-wide logging."""
    settings = get_settings()
    
    # Create logs directory if it doesn't exist
    log_file_path = Path(settings.log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=settings.log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.log_file, encoding='utf-8')
        ],
        force=True # Override any existing configuration
    )
    
    logger = logging.getLogger("app")
    logger.info("Logging initialized.")
    return logger

def get_logger(name: str):
    """Get a named logger."""
    return logging.getLogger(f"app.{name}")
