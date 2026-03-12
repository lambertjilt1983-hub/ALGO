"""
Shared paper trade price updater.
Runs batched price updates and enforces SL/target logic.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Optional, Dict, List

from app.models.trading import PaperTrade
from app.engine.option_signal_generator import _get_kite

# Shared rate limit across all callers (routes + background jobs)
_price_update_cache = {
    "last_update": 0.0,
    "min_interval": 2.0,  # seconds
}


def _paper_profit_protect_status(trade) -> str:
    try:
        entry = float(trade.entry_price or 0)
        stop = float(trade.stop_loss) if trade.stop_loss is not None else None
        side = str(trade.side or "BUY").upper()
        if stop is None or entry <= 0:
            return "SL_HIT"
        if side == "BUY" and stop > entry:
            return "PROFIT_TRAIL"
        if side == "SELL" and stop < entry:
            return "PROFIT_TRAIL"
    except Exception:
        return "SL_HIT"
    return "SL_HIT"


def _fetch_ltp_with_timeout(kite, symbols: List[str], timeout_s: float = 2.5):
    """Fetch LTP with a hard timeout so API route does not hang indefinitely."""
    if not symbols:
        return {}, None

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(kite.ltp, symbols)
    try:
        return future.result(timeout=timeout_s), None
    except FuturesTimeoutError:
        future.cancel()
        return None, f"Price fetch timed out after {timeout_s:.1f}s"
    except Exception as e:
        return None, str(e)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _quote_symbol(trade_symbol: str, index_name: Optional[str] = None) -> str:
    if ":" in trade_symbol:
        return trade_symbol
    upper = trade_symbol.upper()
    if upper.endswith("CE") or upper.endswith("PE"):
        if "SENSEX" in upper:
            return f"BFO:{upper}"
        return f"NFO:{upper}"
    if index_name:
        idx = index_name.upper()
        if idx == "BANKNIFTY":
            return "NSE:NIFTY BANK"
        if idx == "NIFTY":
            return "NSE:NIFTY 50"
        if idx == "FINNIFTY":
            return "NSE:FINNIFTY"
        if idx == "SENSEX":
            return "BSE:SENSEX"
    return f"NSE:{upper}"


def update_open_paper_trades(db, *, force: bool = False) -> Dict:
    """Update prices for OPEN trades and enforce SL logic.

    Returns a summary dict for logging or API response.
    """
    now = time.time()
    if not force and now - _price_update_cache["last_update"] < _price_update_cache["min_interval"]:
        remaining = _price_update_cache["min_interval"] - (now - _price_update_cache["last_update"])
        return {
            "success": False,
            "message": f"Rate limited. Wait {remaining:.1f}s before next update",
            "updated_count": 0,
            "closed_count": 0,
            "total_open": 0,
            "rate_limited": True,
        }

    _price_update_cache["last_update"] = now

    kite = _get_kite()
    if not kite:
        return {
            "success": False,
            "message": "Zerodha credentials missing or invalid",
            "updated_count": 0,
            "closed_count": 0,
            "total_open": 0,
        }

    open_trades: List[PaperTrade] = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
    if not open_trades:
        return {
            "success": True,
            "message": "No open trades to update",
            "updated_count": 0,
            "closed_count": 0,
            "total_open": 0,
        }

    # Batch all quote symbols
    quote_symbols: List[str] = []
    trade_symbol_map: Dict[str, List[PaperTrade]] = {}

    for trade in open_trades:
        try:
            quote_symbol = _quote_symbol(trade.symbol, trade.index_name)
            quote_symbols.append(quote_symbol)
            trade_symbol_map.setdefault(quote_symbol, []).append(trade)
        except Exception:
            continue

    # Avoid duplicate instruments in one broker call.
    quote_symbols = list(dict.fromkeys(quote_symbols))

    quotes, fetch_error = _fetch_ltp_with_timeout(kite, quote_symbols, timeout_s=2.5)
    if fetch_error:
        return {
            "success": False,
            "message": f"Failed to fetch prices: {fetch_error}",
            "updated_count": 0,
            "closed_count": 0,
            "total_open": len(open_trades),
            "timeout": "timed out" in fetch_error.lower(),
        }

    updated_count = 0
    closed_count = 0

    for quote_symbol, trades in trade_symbol_map.items():
        data = quotes.get(quote_symbol) or {}
        live_price = data.get("last_price")
        if live_price is None:
            continue

        new_price = float(live_price)

        for trade in trades:
            try:
                # Smart Profit Booking + Trailing Stop Logic
                # 1) Move SL to breakeven after 35% of target is reached.
                # 2) Close at target (profit booking).
                # 3) If target is exceeded, keep a tighter trailing SL (3pts).
                if trade.side == "BUY":
                    if trade.stop_loss is not None:
                        profit_points = new_price - trade.entry_price
                        target_reached = trade.target is not None and new_price >= trade.target
                        half_target = trade.target is not None and new_price >= (trade.entry_price + (trade.target - trade.entry_price) * 0.35)
                        if half_target and trade.stop_loss < trade.entry_price:
                            trade.stop_loss = round(trade.entry_price, 2)
                            print(
                                f"✅ BREAKEVEN set at {trade.stop_loss} after 35% target reached (Profit: +{profit_points:.1f}pts)"
                            )
                        # Lock-in 12 points profit: once profit >= 12, move SL to entry+12
                        if profit_points >= 12:
                            locked_sl = round(trade.entry_price + 12, 2)
                            if trade.stop_loss < locked_sl:
                                trade.stop_loss = locked_sl
                                print(f"🔒 LOCKED PROFIT: SL moved to {trade.stop_loss} (Profit: +{profit_points:.1f}pts)")
                            # If price starts dropping from last seen price, exit immediately to lock profit
                            if (trade.current_price is not None) and (new_price < trade.current_price):
                                trade.status = "PROFIT_TRAIL"
                                trade.exit_price = new_price
                                trade.exit_time = datetime.utcnow()
                                trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
                                trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                                closed_count += 1
                                print(f"❌ PROFIT-LOCK EXIT: Trade {trade.id} closed at {trade.exit_price} (Profit: ₹{trade.pnl:.2f})")
                                trade.current_price = new_price
                                updated_count += 1
                                continue
                        if target_reached:
                            trade.status = "TARGET_HIT"
                            trade.exit_price = trade.target
                            trade.exit_time = datetime.utcnow()
                            trade.pnl = (trade.target - trade.entry_price) * trade.quantity
                            trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                            closed_count += 1
                            print(
                                f"✅ TARGET HIT: Trade {trade.id} closed at target {trade.target} (Profit: ₹{trade.pnl:.2f})"
                            )
                            trade.current_price = trade.target
                            updated_count += 1
                            continue
                        if trade.target is not None and profit_points > (trade.target - trade.entry_price):
                            new_trailing_sl = round(new_price - 3, 2)
                            if new_trailing_sl > trade.stop_loss:
                                trade.stop_loss = new_trailing_sl
                                print(
                                    f"💎 TARGET EXCEEDED! Trailing SL: {trade.stop_loss} (Profit: +{profit_points:.1f}pts)"
                                )
                else:  # SELL
                    if trade.stop_loss is not None:
                        profit_points = trade.entry_price - new_price
                        target_reached = trade.target is not None and new_price <= trade.target
                        half_target = trade.target is not None and new_price <= (trade.entry_price - (trade.entry_price - trade.target) * 0.35)
                        if half_target and trade.stop_loss > trade.entry_price:
                            trade.stop_loss = round(trade.entry_price, 2)
                            print(
                                f"✅ BREAKEVEN set at {trade.stop_loss} after 35% target reached (Profit: +{profit_points:.1f}pts)"
                            )
                        # Lock-in 12 points profit for shorts: once profit >= 12, move SL to entry-12
                        if profit_points >= 12:
                            locked_sl = round(trade.entry_price - 12, 2)
                            if trade.stop_loss > locked_sl:
                                trade.stop_loss = locked_sl
                                print(f"🔒 LOCKED PROFIT: SL moved to {trade.stop_loss} (Profit: +{profit_points:.1f}pts)")
                            # If price starts rising from last seen price, exit immediately to lock profit
                            if (trade.current_price is not None) and (new_price > trade.current_price):
                                trade.status = "PROFIT_TRAIL"
                                trade.exit_price = new_price
                                trade.exit_time = datetime.utcnow()
                                trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity
                                trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                                closed_count += 1
                                print(f"❌ PROFIT-LOCK EXIT: Trade {trade.id} closed at {trade.exit_price} (Profit: ₹{trade.pnl:.2f})")
                                trade.current_price = new_price
                                updated_count += 1
                                continue
                        if target_reached:
                            trade.status = "TARGET_HIT"
                            trade.exit_price = trade.target
                            trade.exit_time = datetime.utcnow()
                            trade.pnl = (trade.entry_price - trade.target) * trade.quantity
                            trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                            closed_count += 1
                            print(
                                f"✅ TARGET HIT: Trade {trade.id} closed at target {trade.target} (Profit: ₹{trade.pnl:.2f})"
                            )
                            trade.current_price = trade.target
                            updated_count += 1
                            continue
                        if trade.target is not None and profit_points > (trade.entry_price - trade.target):
                            new_trailing_sl = round(new_price + 3, 2)
                            if new_trailing_sl < trade.stop_loss:
                                trade.stop_loss = new_trailing_sl
                                print(
                                    f"💎 TARGET EXCEEDED! Trailing SL: {trade.stop_loss} (Profit: +{profit_points:.1f}pts)"
                                )

                # Check SL using live price (target handled above)
                if trade.side == "BUY":
                    if trade.stop_loss is not None and new_price <= trade.stop_loss:
                        new_price = trade.stop_loss
                        trade.status = _paper_profit_protect_status(trade)
                        trade.exit_price = trade.stop_loss
                        trade.exit_time = datetime.utcnow()
                        trade.pnl = (trade.stop_loss - trade.entry_price) * trade.quantity
                        trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                        closed_count += 1
                        print(f"❌ Trade {trade.id} closed at SL: {trade.stop_loss} (Profit: ₹{trade.pnl:.2f})")
                else:  # SELL
                    if trade.stop_loss is not None and new_price >= trade.stop_loss:
                        new_price = trade.stop_loss
                        trade.status = _paper_profit_protect_status(trade)
                        trade.exit_price = trade.stop_loss
                        trade.exit_time = datetime.utcnow()
                        trade.pnl = (trade.entry_price - trade.stop_loss) * trade.quantity
                        trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                        closed_count += 1
                        print(f"❌ Trade {trade.id} closed at SL: {trade.stop_loss} (Profit: ₹{trade.pnl:.2f})")

                trade.current_price = new_price

                # Calculate P&L while still open or at exit
                if trade.side == "BUY":
                    trade.pnl = (trade.current_price - trade.entry_price) * trade.quantity
                else:
                    trade.pnl = (trade.entry_price - trade.current_price) * trade.quantity

                trade.pnl_percentage = (
                    (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                    if trade.entry_price > 0
                    else 0
                )
                updated_count += 1
            except Exception:
                continue

    db.commit()

    return {
        "success": True,
        "updated_count": updated_count,
        "closed_count": closed_count,
        "total_open": len([t for t in open_trades if t.status == "OPEN"]),
        "message": f"Updated {updated_count} trades, closed {closed_count}",
    }
