from fastapi import APIRouter
from app.engine.option_signal_generator import generate_signals, generate_signals_advanced

router = APIRouter(prefix="/option-signals", tags=["Option Signals"])

@router.get("/intraday")
def get_intraday_option_signals():
    """Get intraday option trading signals for major indices."""
    return {"signals": generate_signals()}


@router.get("/intraday-advanced")
async def get_intraday_option_signals_advanced(
    mode: str = "balanced",
    symbols: str | None = None,
    include_nifty50: bool = False,
):
    """Get intraday signals with trend/news confirmation and adaptive targets."""
    import asyncio
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
        # 15-second timeout for signal generation
        signals = await asyncio.wait_for(
            generate_signals_advanced(mode=mode, symbols=symbol_list, include_nifty50=include_nifty50),
            timeout=15.0
        )
        return {"signals": signals}
    except asyncio.TimeoutError:
        # Return cached signals if generation times out
        from app.engine.option_signal_generator import _signals_cache
        return {"signals": _signals_cache or [], "status": "timeout_using_cache"}
    except Exception as e:
        return {"signals": [], "error": str(e)}
