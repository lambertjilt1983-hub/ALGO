from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_settings
import os

settings = get_settings()

# Use SQLite for development if DATABASE_URL is not set or Postgres is unavailable
db_url = settings.DATABASE_URL
if not db_url or "postgresql" in db_url:
    db_url = "sqlite:///./algotrade.db"

# Configure SQLite connection with proper pooling settings
engine = create_engine(
    db_url, 
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    pool_size=20,  # Increase from default 5
    max_overflow=40,  # Increase from default 10
    pool_pre_ping=True,  # Enable connection health checks
    pool_recycle=3600  # Recycle connections after 1 hour
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
