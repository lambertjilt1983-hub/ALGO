from fastapi import APIRouter
from app.engine.option_signal_generator import generate_signals, generate_signals_advanced

router = APIRouter(prefix="/option-signals", tags=["Option Signals"])

@router.get("/intraday")
def get_intraday_option_signals():
    """Get intraday option trading signals for major indices."""
    return {"signals": generate_signals()}


@router.get("/intraday-advanced")
async def get_intraday_option_signals_advanced(mode: str = "balanced"):
    """Get intraday signals with trend/news confirmation and adaptive targets."""
    return {"signals": await generate_signals_advanced(mode=mode)}
