"""
Configuration management for the data pipeline.
Loads environment variables and provides configuration objects.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Central configuration class for the pipeline."""
    
    # API Configuration
    SPOONACULAR_API_KEY: str = os.getenv("SPOONACULAR_API_KEY", "")
    SPOONACULAR_BASE_URL: str = "https://api.spoonacular.com"
    
    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "data_pipeline")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "admin")
    
    # Pipeline Configuration
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: int = int(os.getenv("RETRY_DELAY", "2"))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/pipeline.log")
    
    # Alerting Configuration (Optional)
    SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    ALERT_EMAIL: Optional[str] = os.getenv("ALERT_EMAIL")
    
    @classmethod
    def get_db_connection_string(cls) -> str:
        """Generate PostgreSQL connection string."""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        if not cls.SPOONACULAR_API_KEY:
            raise ValueError("SPOONACULAR_API_KEY is required")
        if not cls.DB_PASSWORD:
            raise ValueError("DB_PASSWORD is required")
        return True
    
    @classmethod
    def ensure_log_directory(cls):
        """Ensure log directory exists."""
        log_path = Path(cls.LOG_FILE).parent
        log_path.mkdir(parents=True, exist_ok=True)