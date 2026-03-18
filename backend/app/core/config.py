from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path


_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_env_file() -> str:
    env_file = os.environ.get("ENV_FILE", ".env")
    if env_file == "env.qa":
        env_file = ".env.qa"
    elif env_file == "env.local":
        env_file = ".env.local"

    env_path = Path(env_file)
    if not env_path.is_absolute():
        candidate = (_BACKEND_ROOT / env_file).resolve()
        if candidate.exists():
            return str(candidate)
    return str(env_path)

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@YOUR_PRODUCTION_DB_HOST:5432/trading_db"  # Update for production
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY: str = "your-32-char-encryption-key-here"
    FERNET_KEY: str = ""
    
    # Broker Credentials (Zerodha)
    ZERODHA_API_KEY: str = ""
    ZERODHA_API_SECRET: str = ""
    ZERODHA_REDIRECT_URL: str = ""
    
    # Broker Credentials (Upstox)
    UPSTOX_API_KEY: str = ""
    UPSTOX_API_SECRET: str = ""
    UPSTOX_REDIRECT_URL: str = ""
    
    # Broker Credentials (Angel One)
    ANGEL_API_KEY: str = ""
    ANGEL_CLIENT_CODE: str = ""
    
    # Broker Credentials (Groww)
    GROWW_API_KEY: str = ""
    GROWW_API_SECRET: str = ""
    
    # Redis
    REDIS_URL: str = "redis://YOUR_PRODUCTION_REDIS_HOST:6379"  # Update for production
    
    # Logging
    LOG_LEVEL: str = "INFO"

    # Market hours
    MARKET_TIMEZONE: str = "Asia/Kolkata"
    MARKET_HOLIDAYS: str = ""
    
    # Frontend URLs (for OAuth redirects)
    FRONTEND_URL: str = "https://algo-trade-frontend.up.railway.app"
    FRONTEND_ALT_URL: str = "https://algo-trade-frontend.up.railway.app"

    # CORS
    # comma-separated list; include localhost for development
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    
    class Config:
        env_file = _resolve_env_file()
        case_sensitive = True
        extra = "ignore"  # Allow extra fields in .env file

@lru_cache()
def get_settings():
    return Settings()
