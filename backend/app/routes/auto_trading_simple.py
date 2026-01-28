"""Very Simple Auto Trading API (Demo)"""


from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.strategies.market_intelligence import trend_analyzer
import datetime

router = APIRouter(prefix="/autotrade", tags=["Simple Auto Trading"])



# In-memory trade log for demo (replace with DB in production)
trade_log = []

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


@router.post("/analyze")
async def analyze(symbol: str = Query("NIFTY"), balance: float = Query(100000)):
    """
    Analyze and decide trade action for the given symbol and balance.
    Logs the trade in memory and returns the decision.
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
        trade = {
            "symbol": symbol.upper(),
            "decision": decision,
            "change_pct": change_pct,
            "balance": balance,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "active" if decision in ("BUY", "SELL") else "hold"
        }
        trade_log.append(trade)
        return {"decision": decision, "change_pct": change_pct, "symbol": symbol.upper(), "balance": balance, "trade": trade}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze: {str(e)}")


@router.get("/status")
async def status():
    """
    Return a simple status of the auto trading system.
    """
    return {
        "status": "ok",
        "active_trades": len([t for t in trade_log if t["status"] == "active"]),
        "total_trades": len(trade_log),
        "last_trade": trade_log[-1] if trade_log else None
    }


@router.get("/trades/active")
async def trades_active():
    """
    Return all currently active trades.
    """
    return [t for t in trade_log if t["status"] == "active"]


@router.get("/report")
async def report(limit: int = 500):
    """
    Return a report of recent trades (up to limit).
    """
    return trade_log[-limit:]
