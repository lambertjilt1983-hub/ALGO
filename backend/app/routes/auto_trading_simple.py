"""Very Simple Auto Trading API (Demo)"""


from fastapi import APIRouter, HTTPException
from app.strategies.market_intelligence import trend_analyzer
router = APIRouter(prefix="/autotrade", tags=["Simple Auto Trading"])


@router.get("/simple-analyze")
async def simple_analyze(symbol: str = "NIFTY"):
    """
    Fetch real market data for the given symbol (default: NIFTY),
    and return BUY if change_pct > 0.2, SELL if < -0.2, else HOLD.
    """
    try:
        trends = await trend_analyzer.get_market_trends()
        indices = trends.get("indices", {})
        data = indices.get(symbol.upper())
        if not data:
            raise HTTPException(status_code=404, detail=f"No market data for symbol: {symbol}")
        change_pct = data.get("change_percent")
        if change_pct is None:
            raise HTTPException(status_code=500, detail="Market data missing change_percent")
        if change_pct > 0.2:
            decision = "BUY"
        elif change_pct < -0.2:
            decision = "SELL"
        else:
            decision = "HOLD"
        return {"decision": decision, "change_pct": change_pct, "symbol": symbol.upper()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market data: {str(e)}")
