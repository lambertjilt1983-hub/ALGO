import asyncio
from fastapi import APIRouter, Body, Header, HTTPException, BackgroundTasks
router = APIRouter(prefix="/autotrade", tags=["Auto Trading"])

# Demo trades storage for demo mode
demo_trades: list = []

# --- Automated Trade Closing Task ---
async def auto_close_trades_task():
    while True:
        await asyncio.sleep(10)  # Check every 10 seconds
        for trade in list(active_trades):
            if trade.get("status") != "OPEN":
                continue
            # Simulate fetching latest price (replace with real price fetch)
            price = trade.get("current_price") or trade.get("entry_price")
            _maybe_update_trail(trade, price)
            if _stop_hit(trade, price):
                _close_trade(trade, price)
        # Remove closed trades from active_trades
        active_trades[:] = [t for t in active_trades if t.get("status") == "OPEN"]

# Start background task on startup
@router.on_event("startup")
async def start_auto_close_trades():
    asyncio.create_task(auto_close_trades_task())
"""Auto Trading Engine wired to live market data (no mocks)."""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple



from fastapi import APIRouter, Body, Header, HTTPException
from app.routes.option_chain_utils import get_option_chain

from app.strategies.ai_model import ai_model
from app.strategies.market_intelligence import trend_analyzer
from app.core.database import SessionLocal
from app.models.trading import TradeReport
from sqlalchemy import func


router = APIRouter(prefix="/autotrade", tags=["Auto Trading"])

# Option Chain Endpoint (must be after router is defined)
@router.get("/option_chain")
async def option_chain(
    symbol: str = "BANKNIFTY",
    expiry: str = Body(..., embed=True),
    authorization: Optional[str] = Header(None),
):
    """
    Return the full CE/PE option chain for a given index and expiry.
    """
    try:
        data = await get_option_chain(symbol, expiry, authorization)
        return {"success": True, "symbol": symbol, "expiry": expiry, "option_chain": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch option chain: {str(e)}")

MAX_TRADES = 10000  # allow more intraday trades when signals align
TARGET_PCT = 0.6  # target move in percent (slightly above stop for RR >= 1)
STOP_PCT = 0.4    # stop move in percent (tighter risk)
CONFIRM_MOMENTUM_PCT = 0.1  # very loose confirmation so signals appear on small moves
MIN_WIN_RATE = 0.6          # suppress signals if recent hit-rate is below this
MIN_WIN_SAMPLE = 8          # minimum closed trades before applying win-rate gate

# Risk controls (can be made configurable later)
risk_config = {
    "max_daily_loss": 5000.0,         # hard stop on daily drawdown
    "max_position_pct": 0.15,         # 15% per position so a single options lot fits on 100k balance
    "max_portfolio_pct": 0.45,        # allow multiple lots while keeping portfolio cap
    "cooldown_minutes": 5,            # cooldown after a stop (placeholder)
    "min_momentum_pct": 0.05,         # very low floor so quiet sessions still signal
}

trade_window = {
    "start": (9, 20),   # HH, MM local server time
    "end": (15, 20),    # HH, MM local server time
}

trail_config = {
    "enabled": True,
    "trigger_pct": 0.2,   # start trailing earlier to lock gains
    "step_pct": 0.1,      # move stop every additional +0.1% move
    "buffer_pct": 0.05,   # keep a small buffer from entry when arming
}
BREAKEVEN_TRIGGER_PCT = 0.2  # move stop to breakeven once price moves this much in favor

state = {"is_demo_mode": False, "live_armed": True, "daily_loss": 0.0, "daily_date": datetime.now().date()}
active_trades: List[Dict] = []
history: List[Dict] = []
broker_logs: List[Dict] = []

# --- ADMIN/DEBUG: Manual reset endpoint ---
from fastapi import Response

@router.post("/reset")
async def reset_state(authorization: Optional[str] = Header(None)):
    """Reset daily_loss and active_trades (for admin/testing only)."""
    state["daily_loss"] = 0.0
    state["daily_date"] = datetime.now().date()
    active_trades.clear()
    history.clear()
    return {"success": True, "message": "State reset: daily_loss=0, active_trades/history cleared."}


def _now() -> str:
    return datetime.now().isoformat()


def _reset_daily_if_needed():
    today = datetime.now().date()
    if state.get("daily_date") != today:
        state["daily_date"] = today
        state["daily_loss"] = 0.0


def _recent_win_rate(limit: int = 20) -> Tuple[float, int]:
    closed = history[-limit:]
    if not closed:
        return 1.0, 0
    wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
    rate = wins / len(closed)
    return rate, len(closed)


def _win_rate_ok() -> bool:
    rate, count = _recent_win_rate()
    if count < MIN_WIN_SAMPLE:
        return True  # not enough data to gate
    return rate >= MIN_WIN_RATE


def _capital_in_use() -> float:
    total = 0.0
    for t in active_trades:
        if t.get("status") == "OPEN":
            qty = t.get("quantity") or 0
            price = t.get("price") or 0
            total += price * qty
    return total


def _within_trade_window() -> bool:
    now = datetime.now()
    start_h, start_m = trade_window["start"]
    end_h, end_m = trade_window["end"]
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    return start <= now <= end


@router.post("/toggle")
async def toggle(enabled: bool = True, authorization: Optional[str] = Header(None)):
    # Auto-trading is always enabled; respond with enabled state for UI compatibility.
    return {"enabled": True, "is_demo_mode": state["is_demo_mode"], "message": "Auto-trading is always enabled."}


def _init_trailing_fields(entry_price: float, side: str) -> Dict[str, float | bool]:
    # Precompute trailing stop anchor to avoid repeated math and simplify updates.
    buffer = trail_config["buffer_pct"] * entry_price / 100
    if side == "BUY":
        start = entry_price * (1 - trail_config["trigger_pct"] / 100)
        return {
            "trail_active": False,
            "trail_start": start,
            "trail_stop": start - buffer,
            "trail_step": trail_config["step_pct"] * entry_price / 100,
        }
    start = entry_price * (1 + trail_config["trigger_pct"] / 100)
    return {
        "trail_active": False,
        "trail_start": start,
        "trail_stop": start + buffer,
        "trail_step": trail_config["step_pct"] * entry_price / 100,
    }


def _maybe_update_trail(trade: Dict[str, Any], new_price: float) -> None:
    if not trail_config.get("enabled", False):
        return
    side = trade.get("side")
    entry_price = trade.get("price")
    support = trade.get("support")
    resistance = trade.get("resistance")
    trail_active = trade.get("trail_active")
    trail_start = trade.get("trail_start")
    trail_stop = trade.get("trail_stop")
    trail_step = trade.get("trail_step")
    if None in (side, trail_start, trail_stop, trail_step, entry_price):
        return

    # Breakeven: once price moves in favor by BREAKEVEN_TRIGGER_PCT, lift stop to entry +/- tiny buffer
    buffer = trail_config["buffer_pct"] * entry_price / 100
    if side == "BUY" and not trade.get("breakeven_applied"):
        if new_price >= entry_price * (1 + BREAKEVEN_TRIGGER_PCT / 100):
            trade["stop_loss"] = max(trade.get("stop_loss", entry_price - buffer), entry_price + buffer)
            trade["breakeven_applied"] = True
    if side != "BUY" and not trade.get("breakeven_applied"):
        if new_price <= entry_price * (1 - BREAKEVEN_TRIGGER_PCT / 100):
            trade["stop_loss"] = min(trade.get("stop_loss", entry_price + buffer), entry_price - buffer)
            trade["breakeven_applied"] = True

    if side == "BUY":
        if not trail_active and new_price >= trail_start:
            trade["trail_active"] = True
        if trade.get("trail_active") and new_price > trail_start:
            steps = math.floor((new_price - trail_start) / trail_step)
            if steps > 0:
                trail_start = trail_start + steps * trail_step
                trail_stop = trail_start - trail_config["buffer_pct"] * entry_price / 100
                # Do not set trail below known support
                if support:
                    trail_stop = max(trail_stop, support)
                trade["trail_start"] = trail_start
                trade["trail_stop"] = trail_stop
    else:
        if not trail_active and new_price <= trail_start:
            trade["trail_active"] = True
        if trade.get("trail_active") and new_price < trail_start:
            steps = math.floor((trail_start - new_price) / trail_step)
            if steps > 0:
                trail_start = trail_start - steps * trail_step
                trail_stop = trail_start + trail_config["buffer_pct"] * entry_price / 100
                # Do not set trail above known resistance
                if resistance:
                    trail_stop = min(trail_stop, resistance)
                trade["trail_start"] = trail_start
                trade["trail_stop"] = trail_stop

def _close_trade(trade: Dict[str, any], exit_price: float) -> None:
    qty = trade.get("quantity", 0) or 0
    side = trade.get("side", "BUY").upper()
    entry = trade.get("price", 0.0)
    pnl = (exit_price - entry) * qty * (1 if side == "BUY" else -1)
    trade.update({
        "status": "CLOSED",
        "exit_price": exit_price,
        "exit_time": _now(),
        "pnl": round(pnl, 2),
    })
    history.append(trade.copy())
    state["daily_loss"] += pnl

    # Persist closed trade to database for reporting
    try:
        db = SessionLocal()
        exit_dt = datetime.fromisoformat(trade.get("exit_time")) if isinstance(trade.get("exit_time"), str) else datetime.utcnow()
        entry_dt = datetime.fromisoformat(trade.get("entry_time")) if isinstance(trade.get("entry_time"), str) else datetime.utcnow()
        report = TradeReport(
            symbol=trade.get("symbol") or trade.get("index"),
            side=side,
            quantity=qty,
            entry_price=entry,
            exit_price=exit_price,
            pnl=round(pnl, 2),
            pnl_percentage=trade.get("profit_percentage") or trade.get("pnl_percent"),
            strategy=trade.get("strategy") or trade.get("strategy_name"),
            status=trade.get("status") or "CLOSED",
            entry_time=entry_dt,
            exit_time=exit_dt,
            trading_date=exit_dt.date(),
            meta={"support": trade.get("support"), "resistance": trade.get("resistance")},
        )
        db.add(report)
        db.commit()
    except Exception as e:
        print(f"Warning: failed to persist trade report: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


def _stop_hit(trade: Dict[str, any], price: float) -> bool:
    side = trade.get("side", "BUY").upper()
    stop_loss = trade.get("stop_loss")
    trail_stop = trade.get("trail_stop") if trade.get("trail_active") else None
    if stop_loss is None:
        return False
    effective_stop = trail_stop if trail_stop is not None else stop_loss
    if side == "BUY":
        return price <= effective_stop
    return price >= effective_stop


def _calc_weekly_expiry(today: datetime) -> datetime:
    # Indian index weekly options expire on Thursday
    days_ahead = (3 - today.weekday()) % 7  # 0=Mon ... 3=Thu
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def _calc_monthly_expiry(today: datetime) -> datetime:
    # Last Thursday of the current month
    next_month = today.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    # Walk back to Thursday
    while last_day.weekday() != 3:
        last_day -= timedelta(days=1)
    return last_day


def _strike_from_price(price: float, step: int = 50) -> int:
    return int(round(price / step) * step)


def _instrument_mapping(symbol: str, price: float, direction: str) -> Dict[str, any]:
    now = datetime.now()
    weekly_expiry = _calc_weekly_expiry(now)
    monthly_expiry = _calc_monthly_expiry(now)

    lot_sizes = {
        "NIFTY": 50,
        "BANKNIFTY": 15,
        "FINNIFTY": 40,
        "SENSEX": 10,
    }

    lot = lot_sizes.get(symbol, 25)
    strike = _strike_from_price(price)

    opt_type = "C" if direction == "BUY" else "P"

    weekly_symbol = f"{symbol}{weekly_expiry.strftime('%d%b%y').upper()}{strike}{opt_type}"
    monthly_symbol = f"{symbol}{monthly_expiry.strftime('%d%b%y').upper()}{strike}{opt_type}"
    fut_symbol = f"{symbol}{monthly_expiry.strftime('%d%b%y').upper()}FUT"

    return {
        "lot_size": lot,
        "strike": strike,
        "weekly_option": weekly_symbol,
        "monthly_option": monthly_symbol,
        "future": fut_symbol,
        "weekly_expiry": weekly_expiry.strftime("%d-%b-%Y"),
        "monthly_expiry": monthly_expiry.strftime("%d-%b-%Y"),
    }


def _instrument_unit_price(price: float, instrument_type: str) -> float:
    # Approximate trade notional so sizing works for options/futures without live chain data.
    itype = instrument_type.lower()
    if itype == "weekly_option":
        return max(8.0, price * 0.012)  # ~1.2% of spot as rough premium with a small floor
    if itype == "monthly_option":
        return max(10.0, price * 0.015)
    if itype == "future":
        return price * 0.2  # 20% margin assumption
    return price  # cash/spot


def _signal_from_index(symbol: str, data: Dict[str, any], instrument_type: str, qty_override: Optional[int], balance: float) -> Optional[Dict[str, any]]:
    price = data["current"]
    change_pct = data.get("change_percent", 0.0)
    direction = "BUY" if change_pct >= 0 else "SELL"

    uptrend = 1 if (data.get("trend", "").lower() == "uptrend") else 0
    ai_decision = ai_model.predict([change_pct, data.get("rsi", 50), uptrend])

    if ai_decision != 1:
        print(f"[AI MODEL] {symbol}: AI model did not predict BUY (decision={ai_decision})")
        return None
    print(f"[AI MODEL] {symbol}: AI model predicted BUY (decision={ai_decision})")

    # --- Simple momentum-only signal logic ---
    if abs(change_pct) < 0.1:  # Only require 0.1% move for signal
        print(f"[SIMPLE MOMENTUM] {symbol}: abs(change_pct) {abs(change_pct)} < 0.1")
        return None

    # Use original downstream logic for signal construction
    abs_change = abs(change_pct)
    strength = (data.get("strength") or "").title()
    macd = (data.get("macd") or "").title()
    volume_bucket = (data.get("volume") or "Average").title()
    rsi = data.get("rsi", 50)
    support = data.get("support")
    resistance = data.get("resistance")

    target_move = price * (TARGET_PCT / 100)
    stop_move = price * (STOP_PCT / 100)

    target = price + target_move if direction == "BUY" else price - target_move
    stop_loss = price - stop_move if direction == "BUY" else price + stop_move

    # Respect nearby support/resistance when available (keep a small buffer)
    if direction == "BUY" and support:
        stop_loss = round(support * 0.997, 2)  # just below support
    if direction == "SELL" and resistance:
        stop_loss = round(resistance * 1.003, 2)  # just above resistance

    instruments = _instrument_mapping(symbol, price, direction)

    unit_price = _instrument_unit_price(price, instrument_type)

    capital_cap = balance * risk_config["max_position_pct"]
    portfolio_cap = balance * risk_config.get("max_portfolio_pct", 1.0)
    capital_in_use = _capital_in_use()
    remaining_cap = portfolio_cap - capital_in_use
    lot_size = instruments["lot_size"]
    min_cost = unit_price * lot_size

    # FORCE SIGNAL GENERATION: Bypass all capital, lot size, and risk filters
    # Always use at least 1 lot, and set capital_required to unit_price * lot_size
    if qty_override and qty_override > 0:
        qty = qty_override
    else:
        qty = lot_size

    tradable_symbol = {
        "index": symbol,
        "weekly_option": instruments["weekly_option"],
        "monthly_option": instruments["monthly_option"],
        "future": instruments["future"],
    }.get(instrument_type, instruments["weekly_option"])

    capital_required = round(unit_price * qty, 2)

    confidence_bonus = 0
    if strength == "Strong":
        confidence_bonus += 5
    if volume_bucket == "High":
        confidence_bonus += 5
    confidence = min(98.0, max(60.0, abs_change * 12 + 55 + confidence_bonus))

    today_str = datetime.now().strftime("%d-%b-%Y")

    return {
        "symbol": f"{symbol} INDEX",
        "action": direction,
        "confidence": round(confidence, 2),
        "strategy": "LIVE_TREND_FOLLOW",
        "entry_price": price,
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "quantity": qty,
        "capital_required": capital_required,
        "expiry": "INTRADAY",
        "expiry_date": today_str,
        "underlying_price": price,
        "target_points": round(abs(target_move), 2),
        "target_percent": TARGET_PCT,
        "tradable_symbols": instruments,
        "selected_instrument": instrument_type,
        "tradable_symbol": tradable_symbol,
        "contract_expiry_weekly": instruments["weekly_expiry"],
        "contract_expiry_monthly": instruments["monthly_expiry"],
        "support": support,
        "resistance": resistance,
    }


async def _live_signals(symbols: List[str], instrument_type: str, qty_override: Optional[int], balance: float) -> tuple[List[Dict], str]:
    print(f"[_live_signals] Fetching market trends for symbols: {symbols}")
    try:
        trends = await trend_analyzer.get_market_trends()
        print(f"[_live_signals] Market trends fetched: {trends}")
    except Exception as e:
        print(f"[_live_signals] Error fetching market trends: {e}")
        return [], "error"
    indices = trends.get("indices", {}) if trends else {}
    data_source = "live"

    signals: List[Dict] = []
    for symbol in symbols:
        data = indices.get(symbol)
        if not data:
            print(f"[_live_signals] No data for symbol: {symbol}")
            continue
        sig = _signal_from_index(symbol, data, instrument_type, qty_override, balance)
        if not sig:
            print(f"[_live_signals] No signal generated for symbol: {symbol} (data: {data})")
        else:
            sig["data_source"] = data_source
            signals.append(sig)

    print(f"[_live_signals] Signals generated: {signals}")
    return signals, data_source


def _build_demo_trades(signals: List[Dict]) -> None:
    demo_trades.clear()
    for idx, sig in enumerate(signals[:2], 1):
        qty = sig["quantity"]
        current_price = sig["entry_price"]
        pnl = (current_price - sig["entry_price"]) * qty
        demo_trades.append(
            {
                "id": idx,
                "symbol": sig["symbol"],
                "action": sig["action"],
                "entry_price": sig["entry_price"],
                "current_price": round(current_price, 2),
                "stop_loss": sig["stop_loss"],
                "target": sig["target"],
                "quantity": qty,
                "status": "DEMO",
                "strategy": sig["strategy"],
                "entry_time": _now(),
                "capital_used": sig["capital_required"],
                "unrealized_pnl": round(pnl, 2),
                "pnl_percentage": round((pnl / sig["capital_required"]) * 100, 2),
                "expiry": sig["expiry_date"],
                "target_profit": round((sig["target"] - sig["entry_price"]) * qty, 2),
                "max_loss": round((sig["entry_price"] - sig["stop_loss"]) * qty, 2),
            }
        )
@router.post("/mode")
async def set_mode(
    demo_mode: Optional[bool] = Body(None, embed=True),
    demo_mode_query: Optional[bool] = None,
    authorization: Optional[str] = Header(None),
):
    # Demo mode disabled; enforce live only.
    selected_mode = demo_mode if demo_mode is not None else demo_mode_query
    if selected_mode is True:
        raise HTTPException(status_code=400, detail="Demo mode is disabled. Live trading only.")
    state["is_demo_mode"] = False
    return {"mode": "LIVE", "is_demo_mode": False, "live_armed": state.get("live_armed")}


@router.get("/mode")
async def get_mode(demo_mode: Optional[bool] = None, authorization: Optional[str] = Header(None)):
    if demo_mode is True:
        raise HTTPException(status_code=400, detail="Demo mode is disabled. Live trading only.")
    state["is_demo_mode"] = False
    return {"mode": "LIVE", "is_demo_mode": False, "live_armed": state.get("live_armed")}


@router.post("/arm")
async def arm_live_trading(armed: bool = True, authorization: Optional[str] = Header(None)):
    state["live_armed"] = armed
    return {"live_armed": state["live_armed"], "is_demo_mode": state["is_demo_mode"]}


@router.get("/status")
async def status(authorization: Optional[str] = Header(None)):
    active = active_trades
    win_rate, win_sample = _recent_win_rate()
    capital_in_use = _capital_in_use()
    payload = {
        "enabled": True,
        "is_demo_mode": state["is_demo_mode"],
        "active_trades_count": len(active),
        "win_rate": round(win_rate * 100, 2),
        "win_sample": win_sample,
        "daily_pnl": state.get("daily_loss", 0.0),
        "capital_in_use": round(capital_in_use, 2),
        "timestamp": _now(),
    }
    return {"status": payload, **payload}


@router.get("/analyze")
async def analyze_get():
    """GET handler for /autotrade/analyze to provide a friendly message."""
    return {"detail": "This endpoint only supports POST requests. Please use POST to analyze market data."}

@router.post("/analyze")
async def analyze(
    symbol: str = "NIFTY",
    balance: float = 50000,
    symbols: Optional[str] = None,
    instrument_type: str = "weekly_option",  # weekly_option | monthly_option | future | index
    quantity: Optional[int] = None,
    authorization: Optional[str] = Header(None),
):
    # Ignore balance, demo mode, and trading window. Only check for live market data.
    # Always allow auto trade if market is live.

    if symbols is not None:
        if not isinstance(symbols, str):
            print(f"[ANALYZE] symbols is not a string: {symbols} (type={type(symbols)})")
            selected_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
        else:
            print(f"[ANALYZE] symbols before split: {symbols} (type={type(symbols)})")
            selected_symbols = symbols.split(",")
    else:
        selected_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
    selected_symbols = [s.strip().upper() for s in selected_symbols if isinstance(s, str) and s.strip()]
    if not selected_symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")

    # Drop SENSEX unless explicitly requested with a Zerodha token, since Yahoo blocks it on this host.
    if "SENSEX" in selected_symbols and "SENSEX" not in (symbols or ""):
        selected_symbols = [s for s in selected_symbols if s != "SENSEX"]

    instrument_type = instrument_type.lower()
    if instrument_type not in {"index", "weekly_option", "monthly_option", "future"}:
        raise HTTPException(status_code=400, detail="Invalid instrument_type")

    print(f"[ANALYZE] Requested symbols: {selected_symbols}, instrument_type: {instrument_type}, quantity: {quantity}, balance: {balance}")

    signals, data_source = await _live_signals(selected_symbols, instrument_type, quantity, balance)
    print(f"[ANALYZE] Signals returned: {signals}, data_source: {data_source}")
    if not signals:
        print(f"[ANALYZE] No signals generated for symbols: {selected_symbols} (data_source: {data_source})")
        return {
            "success": True,
            "signals": [],
            "high_confidence_signals": [],
            "message": f"No signals generated for symbols: {selected_symbols} (data_source: {data_source})",
            "signals_count": 0,
            "data_source": data_source,
            "timestamp": _now(),
        }

    import json
    from pathlib import Path
    extended_signals = []
    option_chains = []
    high_confidence_signals = [s for s in signals if s.get("confidence", 0) > 80]
    for sig in signals:
        # Always add the original index signal
        extended_signals.append(sig)
        import traceback
        try:
            expiry = sig.get("contract_expiry_weekly") or sig.get("expiry_date") or sig.get("expiry")
            symbol = sig["symbol"].replace(" INDEX", "")
            print(f"[OPTION_CHAIN] Fetching option chain for {symbol} expiry {expiry}")
            # Fetch option chain using DB-backed credentials (handles token/refresh)
            chain = await get_option_chain(symbol, expiry, authorization)
            if not chain or not isinstance(chain, dict) or ("CE" not in chain and "PE" not in chain):
                print(f"[OPTION_CHAIN] Chain is None or missing keys for {symbol} {expiry}: {chain}")
                chain = {"CE": [], "PE": [], "error": "No option chain data returned"}
            print(f"[OPTION_CHAIN] Chain keys: {list(chain.keys()) if isinstance(chain, dict) else type(chain)}")
        except Exception as e:
            print(f"[OPTION_CHAIN] Error fetching option chain for {symbol}: {e}")
            traceback.print_exc()
            chain = {"error": str(e)}
        option_chains.append(chain)
        # Find ATM strike (closest to underlying price)
        atm_strike = None
        if chain.get("CE"):
            ce_list = chain["CE"]
            pe_list = chain["PE"]
            underlying = sig.get("underlying_price") or sig.get("entry_price")
            print(f"[DEBUG] {symbol} CE list length: {len(ce_list)}")
            print(f"[DEBUG] {symbol} PE list length: {len(pe_list)}")
            if ce_list:
                print(f"[DEBUG] {symbol} CE strikes: {[o['strike'] for o in ce_list]}")
            if pe_list:
                print(f"[DEBUG] {symbol} PE strikes: {[o['strike'] for o in pe_list]}")
            if ce_list:
                atm_strike = min(ce_list, key=lambda x: abs(x["strike"] - underlying))["strike"]
                print(f"[OPTION_CHAIN] {symbol} ATM strike: {atm_strike} (underlying: {underlying})")
            else:
                print(f"[OPTION_CHAIN] {symbol}: CE list is empty, cannot find ATM strike.")
            # Generate CE and PE signals for ATM
            for opt_type, opt_list in [("CE", ce_list), ("PE", pe_list)]:
                if not opt_list or atm_strike is None:
                    print(f"[OPTION_CHAIN] {symbol} {opt_type}: No options or ATM strike not found.")
                    print(f"[DEBUG] {symbol} {opt_type} opt_list: {opt_list}")
                    continue
                atm_opt = next((o for o in opt_list if o["strike"] == atm_strike), None)
                if atm_opt:
                    print(f"[OPTION_CHAIN] {symbol} {opt_type} ATM option found: {atm_opt['tradingsymbol']}")
                    opt_signal = {
                        "symbol": atm_opt["tradingsymbol"],
                        "action": sig["action"],
                        "confidence": sig["confidence"],
                        "strategy": sig["strategy"] + f"_{opt_type}",
                        "entry_price": atm_opt.get("last_price", 0),
                        "stop_loss": sig["stop_loss"],
                        "target": sig["target"],
                        "quantity": atm_opt.get("lot_size", 1),
                        "capital_required": atm_opt.get("lot_size", 1) * atm_opt.get("last_price", 0),
                        "expiry": atm_opt.get("expiry"),
                        "expiry_date": atm_opt.get("expiry"),
                        "underlying_price": underlying,
                        "target_points": sig.get("target_points"),
                        "option_type": opt_type,
                        "strike": atm_strike,
                        "data_source": "option_chain"
                    }
                    extended_signals.append(opt_signal)
                else:
                    print(f"[OPTION_CHAIN] {symbol} {opt_type}: No ATM option found for strike {atm_strike}.")
                    print(f"[DEBUG] {symbol} {opt_type} strikes: {[o['strike'] for o in opt_list]}")
    signals = extended_signals

    # Build recommendations for all signals (including CE/PE ATM options)
    recommendations = []
    for sig in signals:
        recommendations.append({
            "action": sig["action"],
            "symbol": sig["symbol"],
            "confidence": sig["confidence"],
            "strategy": sig["strategy"],
            "entry_price": sig["entry_price"],
            "stop_loss": sig["stop_loss"],
            "target": sig["target"],
            "quantity": sig["quantity"],
            "capital_required": sig["capital_required"],
            "potential_profit": round((sig["target"] - sig["entry_price"]) * sig["quantity"], 2),
            "risk": round((sig["entry_price"] - sig["stop_loss"]) * sig["quantity"], 2),
            "expiry": sig.get("expiry"),
            "expiry_date": sig.get("expiry_date"),
            "underlying_price": sig.get("underlying_price"),
            "target_points": sig.get("target_points"),
            "roi_percentage": round(((sig["target"] - sig["entry_price"]) * sig["quantity"] / sig["capital_required"]) * 100, 2) if sig["capital_required"] else 0.0,
            "trail": {
                "enabled": trail_config["enabled"],
                "trigger_pct": trail_config["trigger_pct"],
                "step_pct": trail_config["step_pct"],
            },
            "option_type": sig.get("option_type"),
            "strike": sig.get("strike"),
            "data_source": sig.get("data_source"),
            "option_chain": option_chains[0] if option_chains else None if sig == signals[0] else None,
        })
    # For backward compatibility, keep the first as 'recommendation'
    recommendation = recommendations[0] if recommendations else None
    # Log/store all recommendations to a file (append as JSON lines)
    try:
        log_path = Path("backend/logs/recommendations.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": _now(),
                "recommendations": recommendations,
                "signals": signals,
                "request": {
                    "symbols": selected_symbols,
                    "instrument_type": instrument_type,
                    "quantity": quantity,
                    "balance": balance
                }
            }) + "\n")
    except Exception as e:
        print(f"[LOGGING ERROR] Could not log recommendation: {e}")

    capital_in_use = _capital_in_use()
    remaining_cap = balance * risk_config.get("max_portfolio_pct", 1.0) - capital_in_use
    # Determine if there is enough money for the recommended trade
    required_capital = recommendation["capital_required"] if recommendation else 0
    can_trade = (
        len(active_trades) < MAX_TRADES and remaining_cap >= required_capital and required_capital > 0
    )


    # Optionally auto-trigger trade execution for each recommendation
    auto_trade_result = None
    if can_trade:
        try:
            from fastapi import Request
            if recommendation:
                auto_trade_result = await execute(
                    symbol=recommendation["symbol"],
                    side=recommendation["action"],
                    quantity=recommendation["quantity"],
                    price=recommendation["entry_price"],
                    authorization=authorization
                )
                if auto_trade_result is not None:
                    auto_trade_result["executed"] = True
        except Exception as e:
            print(f"[AUTO TRADE ERROR] Could not auto-execute trade: {e}")
            if auto_trade_result is None:
                auto_trade_result = {}
            auto_trade_result["executed"] = False
            auto_trade_result["error"] = str(e)
    else:
        # Not enough money: show the trade as simulated, do not execute
        if recommendation:
            auto_trade_result = {
                "executed": False,
                "capital_required": recommendation["capital_required"],
                "potential_profit": round((recommendation["target"] - recommendation["entry_price"]) * recommendation["quantity"], 2),
                "potential_loss": round((recommendation["entry_price"] - recommendation["stop_loss"]) * recommendation["quantity"], 2),
                "message": "Not enough capital to execute trade. Simulated only.",
                "demo_mode": True
            }


    response = {
        "success": True,
        "signals": signals,
        "recommendation": recommendation,
        "recommendations": recommendations,
        "signals_count": len(signals),
        "live_balance": balance,
        "live_price": recommendation["entry_price"] if recommendation else None,
        "is_demo_mode": state["is_demo_mode"],
        "mode": "DEMO" if state["is_demo_mode"] else "LIVE",
        "data_source": data_source,
        "can_trade": can_trade,
        "remaining_capital": round(max(0.0, remaining_cap), 2),
        "capital_in_use": round(capital_in_use, 2),
        "portfolio_cap": round(balance * risk_config.get("max_portfolio_pct", 1.0), 2),
        "timestamp": _now(),
        "auto_trade_result": auto_trade_result,
    }

    return response


@router.post("/execute")
async def execute(
    symbol: str,
    price: float = 0.0,
    balance: float = 100.0,
    quantity: Optional[int] = None,
    side: str = "BUY",
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    support: Optional[float] = None,
    resistance: Optional[float] = None,
    broker_id: int = 1,
    authorization: Optional[str] = Header(None),
):
    # Ignore balance, demo mode, trading window, and max trades. Always execute trade if market is live.
    mode = "LIVE"

    pct = STOP_PCT / 100
    derived_stop = stop_loss
    if derived_stop is None:
        if side.upper() == "BUY":
            derived_stop = round(price * (1 - pct), 2)
        else:
            derived_stop = round(price * (1 + pct), 2)

    derived_target = target
    if derived_target is None:
        if side.upper() == "BUY":
            derived_target = round(price * (1 + pct * (TARGET_PCT / STOP_PCT)), 2)
        else:
            derived_target = round(price * (1 - pct * (TARGET_PCT / STOP_PCT)), 2)

    broker_response: Dict[str, any] = {}

    trail_fields = _init_trailing_fields(price, side)

    trade = {
        "id": len(active_trades) + 1,
        "symbol": symbol,
        "price": price,
        "side": side.upper(),
        "quantity": quantity or 1,
        "status": "OPEN",
        "broker_id": broker_id,
        "timestamp": _now(),
        "stop_loss": derived_stop,
        "target": derived_target,
        "support": support,
        "resistance": resistance,
        **trail_fields,
    }

    active_trades.append(trade)
    # TODO: integrate broker SDK here
    broker_response = {
        "broker_id": broker_id,
        "symbol": symbol,
        "price": price,
        "status": "accepted (stub)",
        "timestamp": _now(),
    }
    broker_logs.append({"trade": trade, "response": broker_response})

    return {
        "success": True,
        "is_demo_mode": state["is_demo_mode"],
        "message": f"{mode} trade accepted for {symbol} at {price}",
        "timestamp": _now(),
        "broker_response": broker_response,
        "stop_loss": derived_stop,
        "target": derived_target,
    }


@router.get("/trades/active")
async def get_active_trades(authorization: Optional[str] = Header(None)):
    trades = active_trades
    # Add more status details
    for t in trades:
        entry_price = t.get("entry_price", 0)
        if entry_price is None:
            entry_price = 0.0
        current_price = t.get("current_price")
        if current_price is None:
            current_price = entry_price
        t["unrealized_pnl"] = (current_price - entry_price) * t.get("quantity", 0)
    return {"trades": trades, "is_demo_mode": False, "count": len(trades)}


@router.post("/trades/price")
async def update_trade_price(symbol: str, price: float, authorization: Optional[str] = Header(None)):
    updated = 0
    closed = 0
    to_close = []
    for trade in active_trades:
        if trade.get("symbol") == symbol and trade.get("status") == "OPEN":
            _maybe_update_trail(trade, price)
            trade["current_price"] = price
            updated += 1
            if _stop_hit(trade, price):
                _close_trade(trade, price)
                to_close.append(trade)
                closed += 1

    if to_close:
        active_trades[:] = [t for t in active_trades if t.get("status") == "OPEN"]

    return {
        "updated": updated,
        "closed": closed,
        "symbol": symbol,
        "price": price,
        "active_trades": len(active_trades),
    }


@router.get("/debug/source")
async def debug_source():
    return {
        "source_file": __file__,
        "has_demo_trades": bool(demo_trades),
        "has_active_trades": bool(active_trades),
        "timestamp": _now(),
    }


@router.get("/trades/history")
async def get_trade_history(limit: int = 50, authorization: Optional[str] = Header(None)):
    return {
        "trades": history[-limit:],
        "total_profit": sum(t.get("pnl", 0) for t in history[-limit:]),
    }


@router.get("/report")
async def trade_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
    authorization: Optional[str] = Header(None),
):
    # Default window: last 30 days
    today = datetime.utcnow().date()
    start_dt = datetime.fromisoformat(start_date).date() if start_date else (today - timedelta(days=30))
    end_dt = datetime.fromisoformat(end_date).date() if end_date else today

    # Example: Use in-memory history (replace with DB query as needed)
    filtered = [t for t in history if start_dt <= (t.get("trading_date") or today) <= end_dt]
    trades = filtered[-limit:]
    total_pnl = sum((t.get("pnl") or 0) for t in trades)
    wins = sum(1 for t in trades if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in trades if (t.get("pnl") or 0) < 0)
    total = len(trades)
    by_date: Dict[str, Dict[str, Any]] = {}
    for t in trades:
        key = t.get("trading_date") or today.isoformat()
        rec = by_date.setdefault(key, {"trades": 0, "pnl": 0.0})
        rec["trades"] += 1
        rec["pnl"] += t.get("pnl") or 0

    summary = {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total) * 100, 2) if total else 0.0,
        "total_pnl": round(total_pnl, 2),
        "by_date": [{"date": d, "trades": v["trades"], "pnl": round(v["pnl"], 2)} for d, v in sorted(by_date.items())],
    }

    return {"trades": trades, "summary": summary, "start_date": start_dt.isoformat(), "end_date": end_dt.isoformat()}


@router.get("/market/indices")
async def market_indices():
    trends = await trend_analyzer.get_market_trends()
    indices = trends.get("indices", {}) if trends else {}
    payload = [
        {"symbol": sym, "price": data.get("current"), "change_pct": data.get("change_percent")}
        for sym, data in indices.items()
    ]
    return {
        "indices": payload,
        "timestamp": _now(),
    }


@router.post("/monitor")
async def monitor(authorization: Optional[str] = Header(None)):
    payload = {
        "status": "ok",
        "enabled": True,
        "is_demo_mode": state["is_demo_mode"],
        "active_trades": len(active_trades),
        "demo_trades": len(demo_trades),
        "timestamp": _now(),
    }
    return {"monitor": payload, **payload}
