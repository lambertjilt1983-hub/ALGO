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
    include_fno_universe: bool = False,
    max_symbols: int = 60,
):
    """Get intraday signals with trend/news confirmation and adaptive targets."""
    import asyncio
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
        # Timeout guard; returns cached signals on slow upstream.
        signals = await asyncio.wait_for(
            generate_signals_advanced(
                mode=mode,
                symbols=symbol_list,
                include_nifty50=include_nifty50,
                include_fno_universe=include_fno_universe,
                max_symbols=max_symbols,
            ),
            timeout=40.0
        )
        return {"signals": signals}
    except asyncio.TimeoutError:
        # Return cached signals if generation times out
        from app.engine.option_signal_generator import _signals_cache
        latest = []
        if isinstance(_signals_cache, dict) and _signals_cache:
            latest = max(_signals_cache.values(), key=lambda rec: rec.get("ts", 0)).get("signals", [])
        return {"signals": latest, "status": "timeout_using_cache"}
    except Exception as e:
        return {"signals": [], "error": str(e)}
