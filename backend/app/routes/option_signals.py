
from fastapi import APIRouter
from app.engine.option_signal_generator import generate_signals, generate_signals_advanced

router = APIRouter(prefix="/option-signals", tags=["Option Signals"])

@router.get("/all-quality-options")
async def get_all_quality_option_chains(
    min_quality: int = 85,  # PATCH: Set to 85 as requested
    include_nifty50: bool = True,
    mode: str = "balanced",
    symbols: str | None = None,
):
    """Get all option chains (NSE/Zerodha) with no quality filter (testing mode)."""
    import asyncio
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    try:
        # Use advanced signal generator for best scoring
        signals = await asyncio.wait_for(
            generate_signals_advanced(mode=mode, symbols=symbol_list, include_nifty50=include_nifty50),
            timeout=20.0
        )
        # Filter by quality_score
        filtered = [s for s in signals if s.get("quality_score", 0) >= min_quality]
        # Sort by quality_score descending
        filtered.sort(key=lambda s: s.get("quality_score", 0), reverse=True)
        return {"signals": filtered, "count": len(filtered)}
    except asyncio.TimeoutError:
        from app.engine.option_signal_generator import _signals_cache
        filtered = [s for s in (_signals_cache or []) if s.get("quality_score", 0) >= min_quality]
        filtered.sort(key=lambda s: s.get("quality_score", 0), reverse=True)
        return {"signals": filtered, "count": len(filtered), "status": "timeout_using_cache"}
    except Exception as e:
        return {"signals": [], "error": str(e)}

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
