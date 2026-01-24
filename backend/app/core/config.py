from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/trading_db"  # Update if using cloud DB
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY: str = "your-32-char-encryption-key-here"
    
    # Broker Credentials (Zerodha)
    ZERODHA_API_KEY: str = ""
    ZERODHA_API_SECRET: str = ""
    
    # Broker Credentials (Upstox)
    UPSTOX_API_KEY: str = ""
    UPSTOX_API_SECRET: str = ""
    
    # Broker Credentials (Angel One)
    ANGEL_API_KEY: str = ""
    ANGEL_CLIENT_CODE: str = ""
    
    # Broker Credentials (Groww)
    GROWW_API_KEY: str = ""
    GROWW_API_SECRET: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"  # Update if using cloud Redis
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Frontend URLs (for OAuth redirects)
    FRONTEND_URL: str = "https://algo-trade-frontend.up.railway.app"
    FRONTEND_ALT_URL: str = "https://algo-trade-frontend.up.railway.app"

    # CORS
    ALLOWED_ORIGINS: str = "https://algo-trade-frontend.up.railway.app"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
