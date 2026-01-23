from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, broker, orders, strategies, market_intelligence, auto_trading_simple, test_market, token_refresh
from app.core.database import Base, engine
from app.core.config import get_settings
from app.core.background_tasks import start_background_tasks, stop_background_tasks
from app import brokers  # Import brokers to trigger registration

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
        "http://localhost:5173"
    ],
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
app.include_router(auto_trading_simple.router)  # Using simplified version
app.include_router(token_refresh.router)  # Token refresh and validation endpoints

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup"""
    pass

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
