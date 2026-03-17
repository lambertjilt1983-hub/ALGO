from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_settings

settings = get_settings()

# Use the configured DATABASE_URL in production.
# Fall back to local SQLite only when DATABASE_URL is empty or still a placeholder.
db_url = (settings.DATABASE_URL or "").strip()
placeholder_tokens = (
    "YOUR_PRODUCTION_DB_HOST",
    "user:password@",
)
if not db_url or any(token in db_url for token in placeholder_tokens):
    db_url = "sqlite:///./algotrade.db"

# Accept Heroku/Render style postgres:// URLs.
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

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
