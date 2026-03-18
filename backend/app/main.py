import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import traceback
from app.routes import auth, broker, orders, strategies, market_intelligence, auto_trading_simple, test_market, token_refresh, admin, option_signals, zerodha_postback, paper_trading
from app.core.database import Base, engine, SessionLocal, bootstrap_sqlite_trade_data_if_needed, db_url
from app.core.config import get_settings
from app.core.background_tasks import start_background_tasks, stop_background_tasks
from app import brokers  # Import brokers to trigger registration
from app.auth.service import AuthService

# Create tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not create tables: {e}")

try:
    bootstrap_result = bootstrap_sqlite_trade_data_if_needed()
    print(f"[STARTUP] DB URL: {db_url}")
    print(f"[STARTUP] SQLite bootstrap: {bootstrap_result}")
except Exception as e:
    print(f"[STARTUP] SQLite bootstrap check failed: {e}")


# --- FastAPI lifespan event handler (replaces deprecated on_event) ---
from contextlib import asynccontextmanager
import logging
import importlib.util
from pathlib import Path


def _normalize_origin(origin: str | None) -> str:
    if not origin:
        return ""
    return str(origin).strip().rstrip("/")


def _build_allowed_origins(settings) -> list[str]:
    allowed_origins = [
        normalized
        for normalized in (_normalize_origin(origin) for origin in settings.ALLOWED_ORIGINS.split(","))
        if normalized
    ]
    placeholder_hosts = {
        "https://yourdomain.com",
        "https://www.yourdomain.com",
    }

    if not allowed_origins or placeholder_hosts.intersection(allowed_origins):
        allowed_origins = [
            normalized
            for normalized in (
                _normalize_origin(settings.FRONTEND_URL),
                _normalize_origin(settings.FRONTEND_ALT_URL),
            )
            if normalized
        ]

    if any(h in _normalize_origin(settings.FRONTEND_URL) for h in ("localhost", "127.0.0.1")) or os.getenv("ENV_FILE") == "env.local":
        for host in ("http://localhost:3000", "http://localhost:8000"):
            normalized_host = _normalize_origin(host)
            if normalized_host not in allowed_origins:
                allowed_origins.append(normalized_host)

    for host in ("http://localhost:3000", "http://localhost:3001", "http://localhost:8000"):
        normalized_host = _normalize_origin(host)
        if normalized_host not in allowed_origins:
            allowed_origins.append(normalized_host)

    return allowed_origins

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
        logger.info("[STARTUP] Ensuring default lambert user...")
        AuthService.ensure_default_lambert(db)
        logger.info("[STARTUP] Default lambert ensured.")
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
allowed_origins = _build_allowed_origins(settings)

print(f"[STARTUP] CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# GZip compression – reduces large responses (e.g. trade history) avoiding dev proxy Content-Length mismatch errors
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Logging middleware for debugging CORS issues
@app.middleware("http")
async def log_cors_request(request, call_next):
    should_log = request.url.path.startswith("/autotrade/execute")
    if should_log:
        print(f"[CORS DEBUG] Incoming {request.method} {request.url} Headers: {dict(request.headers)}")

    try:
        response = await call_next(request)
    except Exception as e:
        print(f"[UNHANDLED ERROR] {request.method} {request.url.path}: {e.__class__.__name__}: {e}")
        traceback.print_exc()
        # Keep error responses CORS-readable for the frontend, even when downstream raises.
        response = JSONResponse(
            status_code=500,
            content={"detail": f"Unhandled server error: {e.__class__.__name__}"},
        )

    origin = _normalize_origin(request.headers.get("origin"))
    if origin and origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

    if should_log:
        print(f"[CORS DEBUG] Response status {response.status_code} Headers: {dict(response.headers)}")
    return response

# Include routers
app.include_router(auth.router)
app.include_router(broker.router)
app.include_router(orders.router)
app.include_router(strategies.router)
app.include_router(test_market.router)  # Test endpoint with real data
app.include_router(market_intelligence.router)
app.include_router(option_signals.router)
app.include_router(auto_trading_simple.router, prefix="/autotrade")  # Using simplified version
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
