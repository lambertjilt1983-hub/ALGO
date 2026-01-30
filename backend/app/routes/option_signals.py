from fastapi import APIRouter
from app.engine.option_signal_generator import generate_signals

router = APIRouter(prefix="/option-signals", tags=["Option Signals"])

@router.get("/intraday")
def get_intraday_option_signals():
    """Get intraday option trading signals for major indices."""
    return {"signals": generate_signals()}
