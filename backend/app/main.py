import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.qa')
load_dotenv(dotenv_path)
from dotenv import load_dotenv
load_dotenv('.env.qa')
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, broker, orders, strategies, market_intelligence, auto_trading_simple, test_market, token_refresh, admin, option_signals, zerodha_postback
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

app = FastAPI(
    title="AlgoTrade Pro",
    description="Enterprise Algorithmic Trading Platform",
    version="1.0.0"
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

# Startup and shutdown events
import logging

@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("startup")
    logger.info("[STARTUP] FastAPI startup event triggered.")
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

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    pass

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
