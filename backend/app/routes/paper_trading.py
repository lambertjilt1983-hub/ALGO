"""
Paper Trading API
Track signal performance without real execution
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.trading import PaperTrade

router = APIRouter()

MAX_PAPER_TRADES = 2  # Allow up to 2 paper trades (1 CE + 1 PE)


def _option_kind(symbol: str | None) -> str | None:
    if not symbol:
        return None
    upper = symbol.upper()
    if upper.endswith("CE"):
        return "CE"
    if upper.endswith("PE"):
        return "PE"
    return None


class PaperTradeCreate(BaseModel):
    symbol: str
    index_name: Optional[str] = None
    side: str
    signal_type: Optional[str] = None
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    strategy: str = "professional"
    signal_data: Optional[dict] = None


class PaperTradeUpdate(BaseModel):
    current_price: Optional[float] = None
    status: Optional[str] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None


@router.post("/paper-trades")
def create_paper_trade(trade: PaperTradeCreate, db: Session = Depends(get_db)):
    """Log a new paper trade signal - allow up to 2 open trades (CE + PE)"""
    open_trades = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
    active_count = len(open_trades)

    if active_count >= MAX_PAPER_TRADES:
        return {
            "success": False,
            "message": f"Cannot create new trade. {active_count} active trade(s) already exist.",
            "active_trades": active_count
        }

    kind = _option_kind(trade.symbol)
    if kind:
        active_kinds = {_option_kind(t.symbol) for t in open_trades}
        if kind in active_kinds:
            return {
                "success": False,
                "message": f"Only one {kind} trade can be open at a time.",
                "active_trades": active_count
            }
    
    paper_trade = PaperTrade(
        user_id=1,  # Default user
        symbol=trade.symbol,
        index_name=trade.index_name,
        side=trade.side,
        signal_type=trade.signal_type,
        quantity=trade.quantity,
        entry_price=trade.entry_price,
        current_price=trade.entry_price,
        stop_loss=trade.stop_loss,
        target=trade.target,
        strategy=trade.strategy,
        signal_data=trade.signal_data,
        status="OPEN"
    )
    
    db.add(paper_trade)
    db.commit()
    db.refresh(paper_trade)
    
    return {
        "success": True,
        "trade_id": paper_trade.id,
        "message": "Paper trade logged successfully"
    }


@router.get("/paper-trades/active")
def get_active_paper_trades(db: Session = Depends(get_db)):
    """Get all open paper trades"""
    trades = db.query(PaperTrade).filter(
        PaperTrade.status == "OPEN"
    ).order_by(PaperTrade.entry_time.desc()).all()
    
    return {
        "success": True,
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "index_name": t.index_name,
                "side": t.side,
                "signal_type": t.signal_type,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "current_price": t.current_price,
                "stop_loss": t.stop_loss,
                "target": t.target,
                "pnl": t.pnl,
                "pnl_percentage": t.pnl_percentage,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "signal_data": t.signal_data
            }
            for t in trades
        ]
    }


@router.get("/paper-trades/history")
def get_paper_trade_history(
    days: int = 7,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get closed paper trades history"""
    since_date = date.today() - timedelta(days=days)
    
    trades = db.query(PaperTrade).filter(
        and_(
            PaperTrade.status != "OPEN",
            PaperTrade.trading_date >= since_date
        )
    ).order_by(PaperTrade.exit_time.desc()).limit(limit).all()
    
    return {
        "success": True,
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "index_name": t.index_name,
                "side": t.side,
                "signal_type": t.signal_type,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "current_price": t.current_price,
                "exit_price": t.exit_price,
                "stop_loss": t.stop_loss,
                "target": t.target,
                "status": t.status,
                "pnl": t.pnl,
                "pnl_percentage": t.pnl_percentage,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None
            }
            for t in trades
        ]
    }


@router.put("/paper-trades/{trade_id}")
def update_paper_trade(
    trade_id: int,
    update: PaperTradeUpdate,
    db: Session = Depends(get_db)
):
    """Update paper trade with current price and check exit conditions"""
    trade = db.query(PaperTrade).filter(PaperTrade.id == trade_id).first()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    
    # Update current price
    if update.current_price is not None:
        trade.current_price = update.current_price
        
        # Calculate P&L
        if trade.side == "BUY":
            trade.pnl = (update.current_price - trade.entry_price) * trade.quantity
        else:  # SELL
            trade.pnl = (trade.entry_price - update.current_price) * trade.quantity
        
        trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
        
        # Auto-check exit conditions if still OPEN
        if trade.status == "OPEN":
            # Check target hit
            if trade.target:
                if trade.side == "BUY" and update.current_price >= trade.target:
                    trade.status = "TARGET_HIT"
                    trade.exit_price = update.current_price
                    trade.exit_time = datetime.utcnow()
                elif trade.side == "SELL" and update.current_price <= trade.target:
                    trade.status = "TARGET_HIT"
                    trade.exit_price = update.current_price
                    trade.exit_time = datetime.utcnow()
            
            # Check stop loss hit
            if trade.stop_loss and trade.status == "OPEN":
                if trade.side == "BUY" and update.current_price <= trade.stop_loss:
                    trade.status = "SL_HIT"
                    trade.exit_price = update.current_price
                    trade.exit_time = datetime.utcnow()
                elif trade.side == "SELL" and update.current_price >= trade.stop_loss:
                    trade.status = "SL_HIT"
                    trade.exit_price = update.current_price
                    trade.exit_time = datetime.utcnow()
    
    # Manual status update
    if update.status:
        trade.status = update.status
        if update.status != "OPEN" and not trade.exit_time:
            trade.exit_price = trade.current_price
            trade.exit_time = datetime.utcnow()
    
    db.commit()
    db.refresh(trade)
    
    return {
        "success": True,
        "trade": {
            "id": trade.id,
            "status": trade.status,
            "pnl": trade.pnl,
            "pnl_percentage": trade.pnl_percentage
        }
    }


@router.get("/paper-trades/performance")
def get_performance_stats(days: int = 30, db: Session = Depends(get_db)):
    """Get paper trading performance statistics"""
    since_date = date.today() - timedelta(days=days)
    
    # Get all trades in period
    all_trades = db.query(PaperTrade).filter(
        PaperTrade.trading_date >= since_date
    ).all()
    
    # Get closed trades
    closed_trades = [t for t in all_trades if t.status != "OPEN"]
    
    # Calculate stats
    total_trades = len(closed_trades)
    winning_trades = len([t for t in closed_trades if t.pnl and t.pnl > 0])
    losing_trades = len([t for t in closed_trades if t.pnl and t.pnl < 0])
    
    total_pnl = sum([t.pnl for t in closed_trades if t.pnl]) if closed_trades else 0
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    target_hits = len([t for t in closed_trades if t.status == "TARGET_HIT"])
    sl_hits = len([t for t in closed_trades if t.status == "SL_HIT"])
    
    # Best and worst trades
    best_trade = max(closed_trades, key=lambda t: t.pnl or 0) if closed_trades else None
    worst_trade = min(closed_trades, key=lambda t: t.pnl or 0) if closed_trades else None
    
    # Open positions
    open_positions = [t for t in all_trades if t.status == "OPEN"]
    open_pnl = sum([t.pnl for t in open_positions if t.pnl]) if open_positions else 0
    
    return {
        "success": True,
        "period_days": days,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl_per_trade": round(avg_pnl, 2),
        "target_hits": target_hits,
        "sl_hits": sl_hits,
        "open_positions": len(open_positions),
        "open_pnl": round(open_pnl, 2),
        "best_trade": {
            "symbol": best_trade.symbol,
            "pnl": best_trade.pnl,
            "pnl_percentage": best_trade.pnl_percentage
        } if best_trade else None,
        "worst_trade": {
            "symbol": worst_trade.symbol,
            "pnl": worst_trade.pnl,
            "pnl_percentage": worst_trade.pnl_percentage
        } if worst_trade else None
    }


@router.delete("/paper-trades/{trade_id}")
def delete_paper_trade(trade_id: int, db: Session = Depends(get_db)):
    """Delete a paper trade"""
    trade = db.query(PaperTrade).filter(PaperTrade.id == trade_id).first()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    
    db.delete(trade)
    db.commit()
    
    return {"success": True, "message": "Paper trade deleted"}


@router.post("/paper-trades/close-all")
def close_all_open_trades(db: Session = Depends(get_db)):
    """Close all open paper trades (e.g., end of day)"""
    open_trades = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
    
    for trade in open_trades:
        trade.status = "EXPIRED"
        trade.exit_time = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "closed_count": len(open_trades),
        "message": f"Closed {len(open_trades)} open paper trades"
    }


@router.post("/paper-trades/update-prices")
def update_all_prices(db: Session = Depends(get_db)):
    """Update current prices for all open paper trades using LIVE Zerodha data."""
    from app.engine.paper_trade_updater import update_open_paper_trades

    return update_open_paper_trades(db)


@router.post("/paper-trades/{trade_id}/set-price")
def set_paper_trade_price(trade_id: int, current_price: float, db: Session = Depends(get_db)):
    """Manually set price for a paper trade (for testing/simulation)"""
    trade = db.query(PaperTrade).filter(PaperTrade.id == trade_id).first()
    
    if not trade:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    
    if trade.status != "OPEN":
        return {"success": False, "message": "Trade is already closed"}
    
    trade.current_price = current_price
    
    # Calculate P&L
    if trade.side == "BUY":
        trade.pnl = (trade.current_price - trade.entry_price) * trade.quantity
    else:
        trade.pnl = (trade.entry_price - trade.current_price) * trade.quantity
    
    trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100 if trade.entry_price > 0 else 0
    
    # Check exit conditions
    if trade.stop_loss and trade.side == "BUY" and current_price <= trade.stop_loss:
        trade.status = "SL_HIT"
        trade.exit_price = trade.stop_loss
        trade.exit_time = datetime.utcnow()
        trade.pnl = (trade.stop_loss - trade.entry_price) * trade.quantity
        trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
    elif trade.stop_loss and trade.side == "SELL" and current_price >= trade.stop_loss:
        trade.status = "SL_HIT"
        trade.exit_price = trade.stop_loss
        trade.exit_time = datetime.utcnow()
        trade.pnl = (trade.entry_price - trade.stop_loss) * trade.quantity
        trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
    elif trade.target and trade.side == "BUY" and current_price >= trade.target:
        trade.status = "TARGET_HIT"
        trade.exit_price = trade.target
        trade.exit_time = datetime.utcnow()
        trade.pnl = (trade.target - trade.entry_price) * trade.quantity
        trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
    elif trade.target and trade.side == "SELL" and current_price <= trade.target:
        trade.status = "TARGET_HIT"
        trade.exit_price = trade.target
        trade.exit_time = datetime.utcnow()
        trade.pnl = (trade.entry_price - trade.target) * trade.quantity
        trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
    
    db.commit()
    db.refresh(trade)
    
    return {
        "success": True,
        "trade": {
            "id": trade.id,
            "status": trade.status,
            "current_price": trade.current_price,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "pnl_percentage": trade.pnl_percentage
        }
    }
