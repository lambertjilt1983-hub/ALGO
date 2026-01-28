"""Very Simple Auto Trading API (Demo)"""


from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.strategies.market_intelligence import trend_analyzer
import datetime

router = APIRouter(prefix="/autotrade", tags=["Simple Auto Trading"])




# In-memory trade log and trade ID counter for demo (replace with DB in production)
trade_log = []
trade_id_counter = 1

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
    global trade_id_counter
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

        # Demo values for entry, target, stop_loss
        entry = float(data.get("current")) if data.get("current") not in (None, 0, "0.00", "0") else target / 1.01 if target else 0.0
        target = round(entry * 1.01, 2) if entry else 0.0
        stop_loss = round(entry * 0.99, 2) if entry else 0.0
        strategy = "LIVE_TREND_FOLLOW"

        trade = {
            "id": trade_id_counter,
            "symbol": symbol.upper(),
            "action": decision,
            "entry": entry,
            "target": target,
            "stop_loss": stop_loss,
            "strategy": strategy,
            "time": datetime.datetime.now().isoformat(),
            "change_pct": change_pct,
            "balance": balance,
            "status": "active" if decision in ("BUY", "SELL") else "hold"
        }
        trade_log.append(trade)
        trade_id_counter += 1
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
    Return all currently active trades with full details for frontend table.
    """
    return [
        {
            "id": t["id"],
            "symbol": t["symbol"],
            "action": t["action"],
            "entry": float(t["entry"]),
            "target": float(t["target"]),
            "stop_loss": float(t["stop_loss"]),
            "strategy": t["strategy"],
            "time": t["time"]
        }
        for t in trade_log if t["status"] == "active"
    ]


@router.get("/report")
async def report(limit: int = 500):
    """
    Return a report of recent trades (up to limit).
    """
    return trade_log[-limit:]
