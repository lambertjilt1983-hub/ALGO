import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.qa')
load_dotenv(dotenv_path)
from dotenv import load_dotenv
load_dotenv('.env.qa')
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, broker, orders, strategies, market_intelligence, auto_trading_simple, test_market, token_refresh, admin, option_signals, zerodha_postback, paper_trading
from app.core.database import Base, engine, SessionLocal
from app.core.config import get_settings
from app.core.background_tasks import start_background_tasks, stop_background_tasks
from app import brokers  # Import brokers to trigger registration
from app.auth.service import AuthService

# Create tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not create tables: {e}")


# --- FastAPI lifespan event handler (replaces deprecated on_event) ---
from contextlib import asynccontextmanager
import logging
import importlib.util
from pathlib import Path

def _check_required_dependencies(logger: logging.Logger) -> None:
    requirements_path = Path(__file__).resolve().parent.parent / "requirements.txt"
    if not requirements_path.exists():
        logger.warning("[STARTUP] requirements.txt not found; skipping dependency check.")
        return

    import_map = {
        "python-dotenv": "dotenv",
        "pydantic-settings": "pydantic_settings",
        "python-jose": "jose",
        "passlib": "passlib",
        "psycopg2-binary": "psycopg2",
        "scikit-learn": "sklearn",
        "websocket-client": "websocket",
    }

    missing = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        package = line.split("==")[0].strip()
        module = import_map.get(package, package.replace("-", "_"))
        if importlib.util.find_spec(module) is None:
            missing.append(package)

    if missing:
        logger.error("[STARTUP] Missing Python dependencies: %s", ", ".join(missing))
        logger.error("[STARTUP] Install with: pip install -r backend/requirements.txt")
    else:
        logger.info("[STARTUP] Dependency check passed.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("startup")
    logger.info("[STARTUP] FastAPI startup event triggered.")
    _check_required_dependencies(logger)
    db = SessionLocal()
    try:
        logger.info("[STARTUP] Ensuring default admin user...")
        AuthService.ensure_default_admin(db)
        logger.info("[STARTUP] Default admin ensured.")
    except Exception as e:
        logger.error(f"[STARTUP] Exception during startup: {e}", exc_info=True)
    finally:
        db.close()
        logger.info("[STARTUP] Database session closed.")
    
    # Start background tasks
    logger.info("[STARTUP] Starting background tasks...")
    start_background_tasks()
    logger.info("[STARTUP] Background tasks started.")
    
    yield
    
    # Shutdown
    logger.info("[SHUTDOWN] FastAPI shutdown event triggered.")
    logger.info("[SHUTDOWN] Stopping background tasks...")
    stop_background_tasks()
    logger.info("[SHUTDOWN] Background tasks stopped.")

# Single app instance with all config
app = FastAPI(
    title="AlgoTrade Pro",
    description="Enterprise Algorithmic Trading Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
settings = get_settings()
allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(broker.router)
app.include_router(orders.router)
app.include_router(strategies.router)
app.include_router(test_market.router)  # Test endpoint with real data
app.include_router(market_intelligence.router)
app.include_router(option_signals.router)
app.include_router(auto_trading_simple.router)  # Using simplified version
app.include_router(token_refresh.router)  # Token refresh and validation endpoints
app.include_router(admin.router)  # Admin-only utilities
app.include_router(zerodha_postback.router)  # Zerodha postback endpoint
app.include_router(paper_trading.router)  # Paper trading performance tracking

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to AlgoTrade Pro",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.LOG_LEVEL.lower())
