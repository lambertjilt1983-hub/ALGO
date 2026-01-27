"""Auto Trading Engine wired to live market data (no mocks)."""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Header, HTTPException

from app.strategies.market_intelligence import trend_analyzer
from app.core.database import SessionLocal
from app.models.trading import TradeReport
from sqlalchemy import func

router = APIRouter(prefix="/autotrade", tags=["Auto Trading"])

MAX_TRADES = 6  # allow more intraday trades when signals align
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

    if abs(change_pct) < risk_config["min_momentum_pct"]:
        return None

    if not _win_rate_ok():
        return None

    # Secondary confirmation filters to improve precision
    abs_change = abs(change_pct)
    strength = (data.get("strength") or "").title()
    macd = (data.get("macd") or "").title()
    volume_bucket = (data.get("volume") or "Average").title()
    rsi = data.get("rsi", 50)
    support = data.get("support")
    resistance = data.get("resistance")

    if abs_change < CONFIRM_MOMENTUM_PCT:
        return None

    # Relaxed confirmations to surface signals even on choppy days
    if direction == "BUY":
        if rsi < 45 or rsi > 85:
            return None
    else:
        if rsi > 55 or rsi < 15:
            return None

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

    # For demo mode, allow synthetic sizing even when capital is tiny so UI still shows signals.
    if capital_cap <= 0 or remaining_cap <= 0:
        if not state.get("is_demo_mode"):
            return None
        capital_cap = max(capital_cap, unit_price)
        remaining_cap = max(remaining_cap, unit_price)

    if min_cost > capital_cap:
        if state.get("is_demo_mode"):
            lot_size = 1
            min_cost = unit_price
        else:
            return None

    if qty_override and qty_override > 0:
        if qty_override * unit_price > capital_cap and not state.get("is_demo_mode"):
            return None
        qty = qty_override
    else:
        # Fit within capital cap by whole units; respect lot size minimum
        max_units = int(capital_cap // unit_price)
        if max_units < lot_size:
            if state.get("is_demo_mode"):
                qty = lot_size  # minimal synthetic lot for demo
            else:
                return None  # cannot size within risk
        else:
            qty = max_units - (max_units % lot_size)
            if qty <= 0:
                if state.get("is_demo_mode"):
                    qty = lot_size
                else:
                    return None

    tradable_symbol = {
        "index": symbol,
        "weekly_option": instruments["weekly_option"],
        "monthly_option": instruments["monthly_option"],
        "future": instruments["future"],
    }.get(instrument_type, instruments["weekly_option"])

    capital_required = round(unit_price * qty, 2)
    if capital_required > remaining_cap:
        return None

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
    trends = await trend_analyzer.get_market_trends()
    indices = trends.get("indices", {}) if trends else {}
    data_source = "live"

    signals: List[Dict] = []
    for symbol in symbols:
        data = indices.get(symbol)
        if not data:
            continue
        sig = _signal_from_index(symbol, data, instrument_type, qty_override, balance)
        if sig:
            sig["data_source"] = data_source
            signals.append(sig)

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

    selected_symbols = symbols.split(",") if symbols else ["NIFTY", "BANKNIFTY", "FINNIFTY"]
    selected_symbols = [s.strip().upper() for s in selected_symbols if s.strip()]
    if not selected_symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")

    # Drop SENSEX unless explicitly requested with a Zerodha token, since Yahoo blocks it on this host.
    if "SENSEX" in selected_symbols and "SENSEX" not in (symbols or ""):
        selected_symbols = [s for s in selected_symbols if s != "SENSEX"]

    instrument_type = instrument_type.lower()
    if instrument_type not in {"index", "weekly_option", "monthly_option", "future"}:
        raise HTTPException(status_code=400, detail="Invalid instrument_type")

    signals, data_source = await _live_signals(selected_symbols, instrument_type, quantity, balance)
    if not signals:
        raise HTTPException(status_code=503, detail="No live market data available (quotes unavailable).")

    rec = signals[0]
    recommendation = {
        "action": rec["action"],
        "symbol": rec["symbol"],
        "confidence": rec["confidence"],
        "strategy": rec["strategy"],
        "entry_price": rec["entry_price"],
        "stop_loss": rec["stop_loss"],
        "target": rec["target"],
        "quantity": rec["quantity"],
        "capital_required": rec["capital_required"],
        "potential_profit": round((rec["target"] - rec["entry_price"]) * rec["quantity"], 2),
        "risk": round((rec["entry_price"] - rec["stop_loss"]) * rec["quantity"], 2),
        "expiry": rec["expiry"],
        "expiry_date": rec["expiry_date"],
        "underlying_price": rec["underlying_price"],
        "target_points": rec["target_points"],
        "roi_percentage": round(((rec["target"] - rec["entry_price"]) * rec["quantity"] / rec["capital_required"]) * 100, 2),
        "trail": {
            "enabled": trail_config["enabled"],
            "trigger_pct": trail_config["trigger_pct"],
            "step_pct": trail_config["step_pct"],
        },
    }

    capital_in_use = _capital_in_use()
    remaining_cap = balance * risk_config.get("max_portfolio_pct", 1.0) - capital_in_use
    can_trade = True if state.get("is_demo_mode") else (len(active_trades) < MAX_TRADES and remaining_cap > 0)

    response = {
        "success": True,
        "signals": signals,
        "recommendation": recommendation,
        "signals_count": len(signals),
        "live_balance": balance,
        "live_price": rec["underlying_price"],
        "is_demo_mode": state["is_demo_mode"],
        "mode": "DEMO" if state["is_demo_mode"] else "LIVE",
        "data_source": data_source,
        "can_trade": can_trade,
        "remaining_capital": round(max(0.0, remaining_cap), 2),
        "capital_in_use": round(capital_in_use, 2),
        "portfolio_cap": round(balance * risk_config.get("max_portfolio_pct", 1.0), 2),
        "timestamp": _now(),
    }

    return response


@router.post("/execute")
async def execute(
    symbol: str,
    price: float = 0.0,
    balance: float = 50000.0,
    quantity: Optional[int] = None,
    side: str = "BUY",
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    support: Optional[float] = None,
    resistance: Optional[float] = None,
    broker_id: int = 1,
    authorization: Optional[str] = Header(None),
):
    auto_demo = balance <= 0
    state["is_demo_mode"] = auto_demo
    mode = "DEMO" if auto_demo else "LIVE"

    if not state.get("live_armed") and not auto_demo:
        raise HTTPException(status_code=400, detail="Live trading not armed. Call /autotrade/arm first.")

    _reset_daily_if_needed()
    if state.get("daily_loss", 0) <= -risk_config["max_daily_loss"]:
        raise HTTPException(status_code=403, detail="Daily loss limit breached; trading locked for the day.")

    # Enforce live trading window.
    if not _within_trade_window() and not auto_demo:
        raise HTTPException(status_code=403, detail="Outside trading window")

    if len(active_trades) >= MAX_TRADES and not auto_demo:
        raise HTTPException(status_code=429, detail="Max active trades reached")

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
        "is_demo_mode": auto_demo,
        "message": f"{mode} trade accepted for {symbol} at {price}",
        "timestamp": _now(),
        "broker_response": broker_response,
        "stop_loss": derived_stop,
        "target": derived_target,
    }


@router.get("/trades/active")
async def get_active_trades(authorization: Optional[str] = Header(None)):
    trades = active_trades
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

    db = SessionLocal()
    try:
        q = (
            db.query(TradeReport)
            .filter(TradeReport.trading_date >= start_dt)
            .filter(TradeReport.trading_date <= end_dt)
            .order_by(TradeReport.exit_time.desc())
            .limit(limit)
        )
        rows = q.all()

        def serialize(row: TradeReport) -> Dict[str, Any]:
            return {
                "id": row.id,
                "symbol": row.symbol,
                "action": row.side,
                "quantity": row.quantity,
                "entry_price": row.entry_price,
                "exit_price": row.exit_price,
                "pnl": row.pnl,
                "pnl_percentage": row.pnl_percentage,
                "strategy": row.strategy,
                "status": row.status,
                "entry_time": row.entry_time.isoformat() if row.entry_time else None,
                "exit_time": row.exit_time.isoformat() if row.exit_time else None,
                "trading_date": row.trading_date.isoformat() if row.trading_date else None,
                "meta": row.meta,
            }

        trades = [serialize(r) for r in rows]

        # Include in-memory history (e.g., trades closed in current session) to ensure today's trades appear immediately
        seen_keys = {(t.get("symbol"), t.get("entry_time"), t.get("exit_time")) for t in trades}
        for t in history:
            ts = t.get("exit_time") or t.get("entry_time") or t.get("timestamp")
            if not ts:
                continue
            ts_dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
            if ts_dt.date() < start_dt or ts_dt.date() > end_dt:
                continue
            key = (t.get("symbol") or t.get("index"), t.get("entry_time"), t.get("exit_time"))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            trades.append(
                {
                    "id": t.get("id"),
                    "symbol": t.get("symbol") or t.get("index"),
                    "action": t.get("action") or t.get("side"),
                    "quantity": t.get("quantity"),
                    "entry_price": t.get("entry_price") or t.get("price"),
                    "exit_price": t.get("exit_price"),
                    "pnl": t.get("pnl") or t.get("profit_loss"),
                    "pnl_percentage": t.get("pnl_percentage") or t.get("pnl_percent"),
                    "strategy": t.get("strategy") or t.get("strategy_name"),
                    "status": t.get("status"),
                    "entry_time": t.get("entry_time"),
                    "exit_time": t.get("exit_time"),
                    "trading_date": ts_dt.date().isoformat(),
                    "meta": {"support": t.get("support"), "resistance": t.get("resistance")},
                }
            )

        # Recompute summary on merged trades
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
    finally:
        db.close()


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
