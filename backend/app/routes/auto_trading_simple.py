from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Body, Header, HTTPException
from app.engine.zerodha_order_util import place_zerodha_order

router = APIRouter(prefix="/autotrade", tags=["Auto Trading"])

@router.post("/reset_daily_loss")
async def reset_daily_loss(authorization: Optional[str] = Header(None)):
    state["daily_loss"] = 0.0
    return {"message": "Daily loss reset to 0.0", "daily_loss": state["daily_loss"]}
"""Auto Trading Engine wired to live market data (no mocks)."""

import math
import time
import asyncio
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dt_time
from typing import Any, Dict, List, Optional, Tuple

from app.strategies.market_intelligence import trend_analyzer
from app.engine.option_signal_generator import generate_signals, select_best_signal, _get_kite
from app.engine.paper_trade_updater import _quote_symbol
from app.core.database import SessionLocal
from app.models.trading import TradeReport
from sqlalchemy import func
from app.engine.auto_trading_engine import AutoTradingEngine
from app.engine.zerodha_broker import ZerodhaBroker
from app.engine.simple_momentum_strategy import SimpleMomentumStrategy
from app.core.market_hours import ist_now, is_market_open

router = APIRouter(prefix="/autotrade", tags=["Auto Trading"])

MAX_TRADES = 1  # Only one trade at a time (best signal)
TARGET_PCT = 2.5  # 2.5% target (index/futures sizing)
STOP_PCT = 0.06   # Stop-loss percent fallback (index/futures sizing)
TARGET_POINTS = 15  # Fixed target in points for options
STOP_PCT_OPTIONS = 10.0  # Stop loss percent for options
TRAIL_START_POINTS = 5  # Start trailing after 5 points profit
TRAIL_GAP_POINTS = 10   # Trail by 10 points once active
MAX_STOP_POINTS = 20  # Maximum stop loss in points for options
PROFIT_EXIT_AMOUNT = 800.0  # Currency profit exit for the first trade
LOSS_CAP_AMOUNT = 2000.0    # Currency loss cap for the second trade
CONFIRM_MOMENTUM_PCT = 0.5  # Strong momentum (0.5% minimum move)
MIN_WIN_RATE = 0.70         # High win rate requirement (70%+)
MIN_WIN_SAMPLE = 5          # Require 5 trades to assess win rate
EMERGENCY_STOP_MULTIPLIER = 0.65  # Emergency exit at 65% of stop (6.5 points) to prevent slippage
MAX_LOSS_PER_TRADE_PCT = 1.0  # Never lose more than 1% per trade on capital

# AGGRESSIVE LOSS MANAGEMENT: 3000 daily loss limit, 10000 profit limit
risk_config = {
    "max_daily_loss": 5000.0,        # ₹5000 max daily loss (hardstop to protect capital)
    "max_daily_profit": 10000.0,     # ₹10000 daily profit target (auto-stop at profit)
    "max_per_trade_loss": 600.0,     # ₹600 max loss per trade (prevent single trade disaster)
    "max_consecutive_losses": 0,     # NO consecutive loss limit - immediate loss checking
    "max_position_pct": 0.10,        # 10% max per position
    "max_portfolio_pct": 0.10,       # 10% total exposure
    "cooldown_minutes": 0,           # NO COOLDOWN - trade immediately if conditions met
    "symbol_cooldown_minutes": 10,   # Cooldown after SL on same symbol/root
    "min_momentum_pct": 0.5,         # Very strong momentum (0.5%) - avoid weak entries
    "min_trend_strength": 0.8,       # HIGH trend strength (80%) required - quality only
    "require_trend_confirmation": True,  # STRICT: Confirm trend before entry
    "min_win_rate_threshold": 0.70,  # Only trade if win rate > 70%
    "avoid_high_volatility": True,   # Skip trades in extremely volatile markets
}

trade_window = {
    "start": (9, 15),   # HH, MM IST
    "end": (15, 29),    # HH, MM IST (exit before close)
}

trail_config = {
    "enabled": True,
    "trigger_pct": 0.3,   # Start trailing at 0.3% profit to lock in gains
    "step_pct": 0.15,     # Move stop every additional +0.15% move (wider steps)
    "buffer_pct": 0.1,    # Keep 0.1% buffer to avoid premature exits
}
BREAKEVEN_TRIGGER_PCT = 0.4  # Move stop to breakeven at 0.4% profit (lock in gains earlier)

state = {
    "is_demo_mode": False,
    "live_armed": True,
    "daily_loss": 0.0,
    "daily_profit": 0.0,  # NEW: Track daily profit
    "daily_date": ist_now().date(),
    "consecutive_losses": 0,
    "last_loss_time": None,
    "trading_paused": False,  # NEW: Pause if profit/loss limits hit
    "pause_reason": None,  # NEW: Why trading is paused
    "symbol_cooldowns": {},  # Track recent exits to avoid immediate re-entry
}
active_trades: List[Dict] = []
history: List[Dict] = []
broker_logs: List[Dict] = []
live_price_cache: Dict[str, float] = {}
live_update_state = {
    "failure_count": 0,
    "backoff_until": 0.0,
    "last_duration": 0.0,
}
execute_lock = asyncio.Lock()

# Initialize engine, broker, and strategy
engine = AutoTradingEngine()
zerodha_broker = ZerodhaBroker()
engine.register_broker("zerodha", zerodha_broker)
strategy = SimpleMomentumStrategy()

def _now() -> str:
    return ist_now().isoformat()


def _symbol_root(symbol: str | None) -> str | None:
    if not symbol:
        return None
    match = re.match(r"^([A-Z]+)", symbol.upper())
    return match.group(1) if match else symbol.upper()


def _option_kind(symbol: str | None) -> str | None:
    if not symbol:
        return None
    upper = symbol.upper()
    if upper.endswith("CE"):
        return "CE"
    if upper.endswith("PE"):
        return "PE"
    return None


def _best_signal_by_quality(signals: List[Dict]) -> Optional[Dict]:
    if not signals:
        return None
    return max(signals, key=lambda s: (s.get("quality_score", 0), s.get("confidence", 0)))


def _best_signals_by_kind(signals: List[Dict]) -> Dict[str, Dict]:
    best: Dict[str, Dict] = {}
    for kind in ("CE", "PE"):
        candidates = [s for s in signals if _option_kind(s.get("symbol")) == kind]
        if candidates:
            best[kind] = _best_signal_by_quality(candidates)
    return best


def _apply_fixed_option_levels(signal: Dict) -> Dict:
    kind = _option_kind(signal.get("symbol"))
    if not kind:
        return signal
    entry = float(signal.get("entry_price") or 0)
    action = (signal.get("action") or "BUY").upper()
    if entry <= 0:
        return signal
    stop_move = entry * (STOP_PCT_OPTIONS / 100)
    if action == "SELL":
        target = entry - TARGET_POINTS
        stop_loss = entry + stop_move
    else:
        target = entry + TARGET_POINTS
        stop_loss = entry - stop_move
    qty = int(signal.get("quantity") or 1)
    signal["target"] = round(target, 2)
    signal["stop_loss"] = round(stop_loss, 2)
    signal["target_points"] = float(TARGET_POINTS)
    signal["potential_profit"] = round(abs(target - entry) * qty, 2)
    signal["risk"] = round(abs(entry - stop_loss) * qty, 2)
    return signal


def _pnl_for_trade(trade: Dict[str, Any], price: float) -> float:
    qty = trade.get("quantity", 0) or 0
    side = trade.get("side", "BUY").upper()
    entry = trade.get("price", 0.0) or 0.0
    pnl = (price - entry) * qty
    return pnl if side == "BUY" else -pnl


def _should_exit_by_currency(trade: Dict[str, Any], price: float) -> str | None:
    kind = _option_kind(trade.get("symbol"))
    if not kind:
        return None
    pnl = _pnl_for_trade(trade, price)
    peak_pnl = float(trade.get("peak_pnl") or pnl)
    trade["peak_pnl"] = max(peak_pnl, pnl)
    if kind == "CE":
        # Exit if we hit profit >= threshold and then fall back below it.
        if trade.get("peak_pnl", 0) >= PROFIT_EXIT_AMOUNT and pnl <= PROFIT_EXIT_AMOUNT and trade.get("peak_pnl", 0) > pnl:
            return "PROFIT_TRAIL"
    if kind == "PE" and pnl <= -LOSS_CAP_AMOUNT:
        return "LOSS_CAP"
    return None


def _reset_daily_if_needed():
    today = ist_now().date()
    if state.get("daily_date") != today:
        state["daily_date"] = today
        state["daily_loss"] = 0.0
        state["daily_profit"] = 0.0  # Reset daily profit
        state["consecutive_losses"] = 0
        state["last_loss_time"] = None
        state["trading_paused"] = False  # Reset pause flag
        state["pause_reason"] = None


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
    start_h, start_m = trade_window["start"]
    end_h, end_m = trade_window["end"]
    start = dt_time(start_h, start_m)
    end = dt_time(end_h, end_m)
    return is_market_open(start, end)


def _analyze_trend_strength(symbol: str) -> Dict[str, float]:
    """
    Advanced AI-based trend analysis with multiple indicators
    Returns trend strength score (0-1) and directional bias
    """
    try:
        import yfinance as yf
        import pandas as pd
        import numpy as np
        
        # Fetch multi-timeframe data for comprehensive analysis
        ticker = yf.Ticker(symbol)
        df_5m = ticker.history(period="1d", interval="5m")
        df_15m = ticker.history(period="5d", interval="15m")
        df_1h = ticker.history(period="1mo", interval="1h")
        
        if df_5m.empty or df_15m.empty or df_1h.empty:
            return {"strength": 0.0, "direction": 0, "quality": "poor"}
        
        scores = []
        
        # 1. Moving Average Alignment (30% weight)
        for df, weight in [(df_5m, 0.3), (df_15m, 0.4), (df_1h, 0.3)]:
            if len(df) < 20:
                continue
            df['MA5'] = df['Close'].rolling(5).mean()
            df['MA10'] = df['Close'].rolling(10).mean()
            df['MA20'] = df['Close'].rolling(20).mean()
            
            last = df.iloc[-1]
            # Check alignment: MA5 > MA10 > MA20 (bullish) or reverse (bearish)
            if last['Close'] > last['MA5'] > last['MA10'] > last['MA20']:
                scores.append(weight * 1.0)  # Strong bullish alignment
            elif last['Close'] < last['MA5'] < last['MA10'] < last['MA20']:
                scores.append(weight * 1.0)  # Strong bearish alignment
            elif last['Close'] > last['MA5'] > last['MA10']:
                scores.append(weight * 0.7)  # Moderate bullish
            elif last['Close'] < last['MA5'] < last['MA10']:
                scores.append(weight * 0.7)  # Moderate bearish
            else:
                scores.append(0.0)  # Mixed/choppy
        
        # 2. RSI Momentum (20% weight)
        df_close = df_5m['Close']
        delta = df_close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]
        
        # RSI between 40-60 = weak/choppy, >70 or <30 = strong trend
        if last_rsi > 70 or last_rsi < 30:
            scores.append(0.2 * 1.0)  # Strong momentum
        elif last_rsi > 60 or last_rsi < 40:
            scores.append(0.2 * 0.6)  # Moderate
        else:
            scores.append(0.0)  # Neutral/choppy
        
        # 3. Volume Confirmation (20% weight)
        avg_vol = df_5m['Volume'].rolling(20).mean().iloc[-1]
        recent_vol = df_5m['Volume'].iloc[-5:].mean()
        if recent_vol > avg_vol * 1.2:
            scores.append(0.2 * 1.0)  # Strong volume surge
        elif recent_vol > avg_vol:
            scores.append(0.2 * 0.5)  # Moderate volume
        else:
            scores.append(0.0)  # Weak volume
        
        # 4. Price Action Consistency (30% weight)
        last_5_candles = df_5m.iloc[-5:]
        bullish_candles = sum(1 for _, row in last_5_candles.iterrows() if row['Close'] > row['Open'])
        bearish_candles = 5 - bullish_candles
        
        if bullish_candles >= 4:
            scores.append(0.3 * 1.0)  # Strong bullish consistency
        elif bearish_candles >= 4:
            scores.append(0.3 * 1.0)  # Strong bearish consistency
        elif bullish_candles == 3:
            scores.append(0.3 * 0.6)  # Moderate bullish
        elif bearish_candles == 3:
            scores.append(0.3 * 0.6)  # Moderate bearish
        else:
            scores.append(0.0)  # Choppy/mixed
        
        # Compute final strength score
        total_strength = sum(scores)
        
        # Determine direction
        current_price = df_5m['Close'].iloc[-1]
        ma20_5m = df_5m['Close'].rolling(20).mean().iloc[-1]
        direction = 1 if current_price > ma20_5m else -1
        
        # Quality assessment
        if total_strength >= 0.7:
            quality = "excellent"
        elif total_strength >= 0.5:
            quality = "good"
        elif total_strength >= 0.3:
            quality = "fair"
        else:
            quality = "poor"
        
        return {
            "strength": round(total_strength, 2),
            "direction": direction,
            "quality": quality,
            "rsi": round(last_rsi, 2),
            "volume_ratio": round(recent_vol / avg_vol, 2) if avg_vol > 0 else 0
        }
    
    except Exception as e:
        print(f"[TREND ANALYSIS ERROR] {symbol}: {e}")
        return {"strength": 0.0, "direction": 0, "quality": "error"}


def _detect_market_regime(symbol: str) -> Dict[str, any]:
    """
    AI-based market regime detection to determine optimal trading conditions
    Identifies: TRENDING, RANGING, VOLATILE, QUIET
    """
    try:
        import yfinance as yf
        import numpy as np
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="5m")
        
        if df.empty or len(df) < 50:
            return {"regime": "UNKNOWN", "score": 0.0, "tradeable": False}
        
        # Calculate ATR (Average True Range) for volatility
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(14).mean().iloc[-1]
        avg_price = df['Close'].iloc[-1]
        atr_pct = (atr / avg_price) * 100
        
        # Calculate ADX (Average Directional Index) for trend strength
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = true_range
        atr_14 = tr.rolling(14).mean()
        
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean().iloc[-1]
        
        # Detect regime
        regime = "UNKNOWN"
        tradeable = False
        score = 0.0
        
        if adx > 25 and atr_pct > 0.3:
            regime = "TRENDING"
            tradeable = True  # Best for our strategy
            score = min(1.0, adx / 40)
        elif adx < 20 and atr_pct < 0.2:
            regime = "RANGING"
            tradeable = False  # Avoid choppy markets
            score = 0.2
        elif atr_pct > 0.5:
            regime = "VOLATILE"
            tradeable = False  # Too risky for 10-point stops
            score = 0.1
        else:
            regime = "QUIET"
            tradeable = False  # Not enough momentum
            score = 0.3
        
        return {
            "regime": regime,
            "adx": round(adx, 2),
            "atr_pct": round(atr_pct, 3),
            "tradeable": tradeable,
            "score": round(score, 2),
            "recommendation": "ENTER" if tradeable and score > 0.6 else "WAIT"
        }
    
    except Exception as e:
        print(f"[REGIME DETECTION ERROR] {symbol}: {e}")
        return {"regime": "ERROR", "score": 0.0, "tradeable": False}


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
    pnl_percentage = (pnl / (entry * qty) * 100) if entry and qty else 0.0
    exit_dt = datetime.utcnow()
    trade.update({
        "status": "CLOSED",
        "exit_price": exit_price,
        "exit_time": exit_dt.isoformat(),
        "pnl": round(pnl, 2),
        "pnl_percentage": round(pnl_percentage, 2),
    })
    root = _symbol_root(trade.get("symbol") or trade.get("index"))
    if root:
        state.setdefault("symbol_cooldowns", {})[root] = {
            "status": trade.get("status"),
            "exit_time": exit_dt.isoformat(),
        }
    history.append(trade.copy())
    
    # Track daily P&L (both loss and profit)
    state["daily_loss"] += pnl
    state["daily_profit"] = state.get("daily_profit", 0.0) + max(0, pnl)  # Track only wins
    
    print(f"\n[TRADE CLOSED] P&L: ₹{pnl:.2f}")
    print(f"  Daily Loss: ₹{state['daily_loss']:.2f} / ₹{risk_config['max_daily_loss']}")
    print(f"  Daily Profit: ₹{state['daily_profit']:.2f} / ₹{risk_config['max_daily_profit']}")
    
    # Track consecutive losses for risk management (NO COOLDOWN - just log)
    if pnl < 0:
        state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
        state["last_loss_time"] = datetime.now()
        print(f"  ⚠️ Consecutive losses: {state['consecutive_losses']}")
    else:
        state["consecutive_losses"] = 0
        print(f"  ✅ Win! Resetting consecutive loss counter")

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
            pnl_percentage=round(pnl_percentage, 2),
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


def close_all_active_trades(reason: str = "Market close") -> int:
    """Force-close all open active trades with a market exit order."""
    if not active_trades:
        return 0

    closed_count = 0
    for trade in list(active_trades):
        if trade.get("status") != "OPEN":
            continue

        symbol = trade.get("symbol")
        qty = int(trade.get("quantity") or 0)
        side = (trade.get("side") or "BUY").upper()
        exit_side = "SELL" if side == "BUY" else "BUY"
        exchange = trade.get("exchange") or "NFO"
        product = trade.get("product") or "MIS"
        exit_price = trade.get("current_price") or trade.get("price") or 0.0

        if not symbol or qty <= 0:
            continue

        exit_order = place_zerodha_order(
            symbol=symbol,
            quantity=qty,
            side=exit_side,
            order_type="MARKET",
            product=product,
            exchange=exchange,
        )

        if exit_order.get("success"):
            trade["exit_reason"] = reason
            trade["exit_order_id"] = exit_order.get("order_id")
            _close_trade(trade, exit_price)
            closed_count += 1
        else:
            trade["exit_error"] = exit_order.get("error")

    if closed_count > 0:
        active_trades[:] = [t for t in active_trades if t.get("status") == "OPEN"]

    return closed_count


def _stop_hit(trade: Dict[str, any], price: float) -> bool:
    """Check if stop loss is hit, with emergency stop buffer to prevent slippage losses"""
    side = trade.get("side", "BUY").upper()
    stop_loss = trade.get("stop_loss")
    trail_stop = trade.get("trail_stop") if trade.get("trail_active") else None
    if stop_loss is None:
        return False
    
    effective_stop = trail_stop if trail_stop is not None else stop_loss
    entry_price = trade.get("price", 0)
    
    # Calculate emergency stop (slightly before actual stop to prevent slippage)
    if entry_price > 0:
        stop_distance = abs(entry_price - effective_stop)
        emergency_distance = stop_distance * EMERGENCY_STOP_MULTIPLIER
        if side == "BUY":
            emergency_stop = entry_price - emergency_distance
        else:
            emergency_stop = entry_price + emergency_distance
    else:
        emergency_stop = effective_stop
    
    # Check emergency stop first (tighter), then regular stop
    if side == "BUY":
        return price <= emergency_stop or price <= effective_stop
    return price >= emergency_stop or price >= effective_stop


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

    # Require minimum momentum confirmation
    if abs_change < CONFIRM_MOMENTUM_PCT:
        return None
    
    # Additional quality filters for better win rate
    # Require decent volume - avoid low liquidity signals
    if volume_bucket.lower() == "low":
        return None
    
    # For strong directional moves, prefer strong strength confirmation
    if abs_change > 0.5:  # Significant move
        if strength.lower() not in ["strong", "moderate"]:
            return None

    # Stricter RSI filters to avoid extreme conditions and improve win rate
    if direction == "BUY":
        # For BUY: RSI should be 40-70 (avoid overbought and extreme oversold)
        if rsi < 40 or rsi > 70:
            return None
    else:  # SELL
        # For SELL: RSI should be 30-60 (avoid oversold and extreme overbought)
        if rsi > 60 or rsi < 30:
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
    print(f"[_live_signals] Generating signals for symbols: {symbols}, instrument: {instrument_type}")
    data_source = "zerodha_option_chain"

    option_signals = generate_signals()
    if not option_signals:
        return [], data_source

    signals: List[Dict] = []
    for raw in option_signals:
        if raw.get("error"):
            continue
        index = (raw.get("index") or "").upper()
        if symbols and index not in symbols:
            continue

        entry_price = float(raw.get("entry_price") or 0)
        target = float(raw.get("target") or 0)
        stop_loss = float(raw.get("stop_loss") or 0)
        qty = int(qty_override or raw.get("quantity") or 1)
        if entry_price <= 0 or target <= 0 or stop_loss <= 0:
            continue

        action = (raw.get("action") or "BUY").upper()
        symbol = raw.get("symbol") or index
        capital_required = round(entry_price * qty, 2)
        target_points = round(target - entry_price, 2)

        sig = {
            "action": action,
            "symbol": symbol,
            "index": index,
            "confidence": raw.get("confidence", 0),
            "quality_score": raw.get("quality_score", 0),
            "confirmation_score": raw.get("confirmation_score", raw.get("confidence", 0)),
            "strategy": raw.get("strategy", "ATM Option"),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "quantity": qty,
            "capital_required": capital_required,
            "potential_profit": round((target - entry_price) * qty, 2),
            "risk": round((entry_price - stop_loss) * qty, 2),
            "expiry": raw.get("expiry_date") or raw.get("expiry"),
            "expiry_date": raw.get("expiry_date") or raw.get("expiry"),
            "underlying_price": entry_price,
            "target_points": target_points,
            "data_source": data_source,
        }
        sig = _apply_fixed_option_levels(sig)
        signals.append(sig)
        print(f"[_live_signals] ✓ Signal generated for {index}: {action} {symbol} @ ₹{entry_price}")

    # Sort by quality score so best is first for recommendation
    signals.sort(key=lambda s: (s.get("quality_score", 0), s.get("confidence", 0)), reverse=True)
    print(f"[_live_signals] ✓ Generated {len(signals)} signals total")
    return signals, data_source


def _build_demo_trades(signals: List[Dict]) -> None:
    demo_trades.clear()
    best_by_kind = _best_signals_by_kind(signals)
    preferred = []
    if best_by_kind.get("CE"):
        preferred.append(best_by_kind["CE"])
    if best_by_kind.get("PE"):
        preferred.append(best_by_kind["PE"])
    if len(preferred) < 2:
        for sig in signals:
            if sig not in preferred:
                preferred.append(sig)
            if len(preferred) >= 2:
                break
    for idx, sig in enumerate(preferred[:2], 1):
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
        "daily_loss": state.get("daily_loss", 0.0),
        "daily_loss_limit": risk_config["max_daily_loss"],
        "daily_profit": state.get("daily_profit", 0.0),
        "daily_profit_limit": risk_config["max_daily_profit"],
        "trading_paused": state.get("trading_paused", False),
        "pause_reason": state.get("pause_reason"),
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
    print(f"\n[API /analyze] Called with: symbols={symbols}, balance={balance}, mode={'LIVE' if balance > 0 else 'DEMO'}")
    auto_demo = balance <= 0
    state["is_demo_mode"] = auto_demo

    if not state.get("live_armed") and not auto_demo:
        raise HTTPException(status_code=400, detail="Live trading not armed. Call /autotrade/arm first.")

    _reset_daily_if_needed()
    if state.get("daily_loss", 0) <= -risk_config["max_daily_loss"]:
        raise HTTPException(status_code=403, detail="Daily loss limit breached; trading locked for the day.")
    
    # Check consecutive losses - prevent trading after multiple losses
    if state.get("consecutive_losses", 0) >= risk_config["max_consecutive_losses"]:
        last_loss = state.get("last_loss_time")
        cooldown_minutes = risk_config.get("cooldown_minutes", 15)
        if last_loss:
            elapsed = (datetime.now() - last_loss).total_seconds() / 60
            if elapsed < cooldown_minutes:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Consecutive loss limit reached ({risk_config['max_consecutive_losses']}). Cooling down for {int(cooldown_minutes - elapsed)} more minutes."
                )
            else:
                # Reset after cooldown period
                state["consecutive_losses"] = 0
                state["last_loss_time"] = None
    
    # Check per-trade loss limit before entry
    potential_loss = abs(trade.price - (trade.stop_loss or (trade.price * (1 - STOP_PCT/100)))) * (trade.quantity or 1)
    if potential_loss > risk_config.get("max_per_trade_loss", 500):
        raise HTTPException(
            status_code=403,
            detail=f"Potential loss ₹{potential_loss:.2f} exceeds per-trade limit ₹{risk_config['max_per_trade_loss']}"
        )

    # Enforce live trading window.
    if not _within_trade_window():
        raise HTTPException(status_code=403, detail="Outside trading window")

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

    rec = _best_signal_by_quality(signals) or signals[0]
    best_by_kind = _best_signals_by_kind(signals)
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
    active_kinds = {_option_kind(t.get("symbol")) for t in active_trades if t.get("status") == "OPEN"}
    available_sides = {
        "CE": "CE" not in active_kinds,
        "PE": "PE" not in active_kinds,
    }

    response = {
        "success": True,
        "signals": signals,
        "recommendation": recommendation,
        "best_signals": best_by_kind,
        "signals_count": len(signals),
        "live_balance": balance,
        "live_price": rec["underlying_price"],
        "is_demo_mode": state["is_demo_mode"],
        "mode": "DEMO" if state["is_demo_mode"] else "LIVE",
        "data_source": data_source,
        "can_trade": can_trade,
        "available_sides": available_sides,
        "remaining_capital": round(max(0.0, remaining_cap), 2),
        "capital_in_use": round(capital_in_use, 2),
        "portfolio_cap": round(balance * risk_config.get("max_portfolio_pct", 1.0), 2),
        "timestamp": _now(),
    }

    return response


class TradeRequest(BaseModel):
    symbol: str
    price: float = 0.0
    balance: float = 50000.0
    quantity: Optional[int] = None
    side: str = "BUY"
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    broker_id: int = 1
    expiry: Optional[str] = None


class CloseTradeRequest(BaseModel):
    trade_id: Optional[int] = None
    symbol: Optional[str] = None

@router.post("/execute")
async def execute(
    trade: TradeRequest,
    authorization: Optional[str] = Header(None),
):
    auto_demo = trade.balance <= 0
    state["is_demo_mode"] = auto_demo
    mode = "DEMO" if auto_demo else "LIVE"

    print(f"\n[API /execute] Called - {mode} TRADE")
    print(f"[API /execute] Symbol: {trade.symbol}, Side: {trade.side}, Price: {trade.price}, Qty: {trade.quantity or 1}")

    if not state.get("live_armed") and not auto_demo:
        raise HTTPException(status_code=400, detail="Live trading not armed. Call /autotrade/arm first.")

    _reset_daily_if_needed()
    
    # ═══════════════════════════════════════════════════════════════
    # LOSS & PROFIT LIMIT CHECKS (NEW)
    # ═══════════════════════════════════════════════════════════════
    
    # Check if daily loss limit breached
    if state.get("daily_loss", 0) <= -risk_config["max_daily_loss"]:
        state["trading_paused"] = True
        state["pause_reason"] = f"Daily loss limit (₹{risk_config['max_daily_loss']}) breached"
        raise HTTPException(
            status_code=403,
            detail=f"🛑 Daily loss limit ₹{risk_config['max_daily_loss']} breached. Trading locked for protection."
        )
    
    # Check if daily profit target reached (NEW!)
    if state.get("daily_profit", 0) >= risk_config["max_daily_profit"]:
        state["trading_paused"] = True
        state["pause_reason"] = f"Daily profit target (₹{risk_config['max_daily_profit']}) reached"
        raise HTTPException(
            status_code=403,
            detail=f"🎉 Daily profit target ₹{risk_config['max_daily_profit']} reached! Trading paused. Enjoy your profits!"
        )
    
    # Check if trading is paused due to limits
    if state.get("trading_paused", False):
        raise HTTPException(
            status_code=403,
            detail=f"Trading paused: {state.get('pause_reason', 'System pause')}"
        )

    root = _symbol_root(trade.symbol)
    if root:
        cooldown_minutes = risk_config.get("symbol_cooldown_minutes", 0)
        if cooldown_minutes > 0:
            recent = state.get("symbol_cooldowns", {}).get(root)
            if recent and recent.get("status") in {"SL_HIT", "STOPPED"}:
                try:
                    last_exit = datetime.fromisoformat(recent.get("exit_time"))
                except Exception:
                    last_exit = None
                if last_exit:
                    elapsed = (datetime.utcnow() - last_exit).total_seconds() / 60
                    if elapsed < cooldown_minutes:
                        raise HTTPException(
                            status_code=403,
                            detail=f"Cooldown active for {root}. Wait {int(cooldown_minutes - elapsed)} min after SL."
                        )
    
    # ═══════════════════════════════════════════════════════════════
    # ADVANCED AI-BASED ENTRY VALIDATION (NEW)
    # ═══════════════════════════════════════════════════════════════
    
    if not auto_demo and risk_config.get("require_trend_confirmation", True):
        # Step 1: Market Regime Detection
        print(f"[AI ANALYSIS] Detecting market regime for {trade.symbol}...")
        regime = _detect_market_regime(trade.symbol)
        print(f"[AI ANALYSIS] Regime: {regime['regime']} | ADX: {regime.get('adx', 0)} | Tradeable: {regime['tradeable']}")
        
        if not regime["tradeable"]:
            raise HTTPException(
                status_code=403, 
                detail=f"Market regime '{regime['regime']}' not suitable for trading. Recommendation: {regime.get('recommendation', 'WAIT')}"
            )
        
        # Step 2: Trend Strength Analysis
        print(f"[AI ANALYSIS] Analyzing trend strength for {trade.symbol}...")
        trend = _analyze_trend_strength(trade.symbol)
        print(f"[AI ANALYSIS] Trend Strength: {trend['strength']} | Quality: {trend['quality']} | Direction: {trend['direction']}")
        
        min_trend = risk_config.get("min_trend_strength", 0.7)
        if trend["strength"] < min_trend:
            raise HTTPException(
                status_code=403,
                detail=f"Trend strength {trend['strength']} below minimum {min_trend}. Quality: {trend['quality']}"
            )
        
        # Step 3: Direction Confirmation
        expected_direction = 1 if trade.side.upper() == "BUY" else -1
        if trend["direction"] != expected_direction:
            raise HTTPException(
                status_code=403,
                detail=f"Trend direction mismatch: {trade.side} signal but trend is {'DOWN' if trend['direction'] < 0 else 'UP'}"
            )
        
        # Step 4: Volume & RSI Validation
        if trend.get("volume_ratio", 0) < 1.0:
            print(f"[AI WARNING] Low volume ({trend['volume_ratio']}x avg) - proceed with caution")
        
        if trend.get("rsi", 50) > 75 or trend.get("rsi", 50) < 25:
            print(f"[AI WARNING] Extreme RSI ({trend['rsi']}) - potential reversal risk")
        
        print(f"[AI ANALYSIS] ✓ ALL CHECKS PASSED - Trade approved with {trend['quality']} setup quality")
    
    # ═══════════════════════════════════════════════════════════════

    # Enforce live trading window.
    if not _within_trade_window() and not auto_demo:
        raise HTTPException(status_code=403, detail="Outside trading window")


    option_kind = _option_kind(trade.symbol)

    # ═══════════════════════════════════════════════════════════════
    # 10-POINT MAX STOP LOSS VALIDATION (NEW)
    # ═══════════════════════════════════════════════════════════════
    
    pct = STOP_PCT / 100
    derived_stop = trade.stop_loss
    if option_kind:
        stop_move = trade.price * (STOP_PCT_OPTIONS / 100)
        if trade.side.upper() == "SELL":
            derived_stop = round(trade.price + stop_move, 2)
        else:
            derived_stop = round(trade.price - stop_move, 2)
    elif derived_stop is None:
        if trade.side.upper() == "BUY":
            derived_stop = round(trade.price * (1 - pct), 2)
        else:
            derived_stop = round(trade.price * (1 + pct), 2)
    
    # Calculate stop loss in points
    stop_points = abs(trade.price - derived_stop)
    if stop_points > MAX_STOP_POINTS and not auto_demo:
        # Adjust to max allowed points
        if trade.side.upper() == "BUY":
            derived_stop = trade.price - MAX_STOP_POINTS
        else:
            derived_stop = trade.price + MAX_STOP_POINTS
        print(f"[RISK CONTROL] Stop loss adjusted to {MAX_STOP_POINTS} points: ₹{derived_stop:.2f}")
        stop_points = abs(trade.price - derived_stop)
    
    # Validate max loss amount
    qty = trade.quantity or 1
    potential_loss = stop_points * qty
    max_loss_allowed = risk_config.get("max_per_trade_loss", 650)
    
    if potential_loss > max_loss_allowed and not auto_demo:
        raise HTTPException(
            status_code=403,
            detail=f"Potential loss ₹{potential_loss:.2f} exceeds limit ₹{max_loss_allowed}. Reduce qty or tighten stop."
        )
    
    # ═══════════════════════════════════════════════════════════════

    derived_target = trade.target
    if option_kind:
        if trade.side.upper() == "SELL":
            derived_target = round(trade.price - TARGET_POINTS, 2)
        else:
            derived_target = round(trade.price + TARGET_POINTS, 2)
    elif derived_target is None:
        if trade.side.upper() == "BUY":
            derived_target = round(trade.price * (1 + pct * (TARGET_PCT / STOP_PCT)), 2)
        else:
            derived_target = round(trade.price * (1 - pct * (TARGET_PCT / STOP_PCT)), 2)

    async with execute_lock:
        if len(active_trades) >= MAX_TRADES and not auto_demo:
            raise HTTPException(status_code=429, detail="Max active trades reached")

        if not auto_demo:
            existing = next((t for t in active_trades if t.get("status") == "OPEN"), None)
            if existing:
                raise HTTPException(status_code=429, detail="Another trade is already open")

        broker_response: Dict[str, any] = {}

        trail_fields = _init_trailing_fields(trade.price, trade.side)

        trade_obj = {
            "id": len(active_trades) + 1,
            "symbol": trade.symbol,
            "price": trade.price,
            "side": trade.side.upper(),
            "quantity": trade.quantity or 1,
            "status": "OPEN",
            "broker_id": trade.broker_id,
            "exchange": "NFO",
            "product": "MIS",
            "timestamp": _now(),
            "stop_loss": derived_stop,
            "target": derived_target,
            "support": trade.support,
            "resistance": trade.resistance,
            **trail_fields,
        }

        # --- REAL ZERODHA ORDER PLACEMENT ---
        # Map your signal to the correct Zerodha symbol (tradingsymbol)
        zerodha_symbol = trade.symbol  # You may need to convert to e.g. 'BANKNIFTY24FEB48000CE'
        print(f"[API /execute] ▶ Placing {mode} order to Zerodha...")
        print(f"[API /execute] ▶ Order Details: {zerodha_symbol}, {trade.quantity or 1} qty, {trade.side} at ₹{trade.price}")
        real_order = place_zerodha_order(
            symbol=zerodha_symbol,
            quantity=trade.quantity or 1,
            side=trade.side,
            order_type="MARKET",
            product="MIS",
            exchange="NFO"  # Use 'NFO' for options
        )
        if real_order["success"]:
            print(f"[API /execute] ✓ Zerodha order ACCEPTED - Order ID: {real_order.get('order_id', 'N/A')}")
            broker_response = real_order
            active_trades.append(trade_obj)
        else:
            print(f"[API /execute] ✗ Zerodha order REJECTED - Error: {real_order.get('error', 'Unknown')}")
            return {
                "success": False,
                "message": real_order["error"],
                "timestamp": _now(),
            }

        broker_logs.append({"trade": trade_obj, "response": broker_response})

        return {
            "success": True,
            "is_demo_mode": auto_demo,
            "message": f"{mode} trade accepted for {trade.symbol} at {trade.price}",
            "timestamp": _now(),
            "broker_response": broker_response,
            "stop_loss": derived_stop,
            "target": derived_target,
        }


@router.get("/trades/active")
async def get_active_trades(authorization: Optional[str] = Header(None)):
    print(f"[API /trades/active] Returning {len(active_trades)} active trades from Zerodha")
    trades = active_trades
    return {"trades": trades, "is_demo_mode": False, "count": len(trades)}


@router.post("/trades/update-prices")
async def update_live_trade_prices(authorization: Optional[str] = Header(None)):
    now = time.time()
    if live_update_state["backoff_until"] > now:
        return {
            "success": False,
            "updated_count": 0,
            "message": "Zerodha throttled - backing off",
            "retry_after": round(live_update_state["backoff_until"] - now, 2),
        }

    open_trades = [t for t in active_trades if t.get("status") == "OPEN"]
    if not open_trades:
        return {"success": True, "updated_count": 0, "message": "No open trades to update"}

    kite = _get_kite()
    if not kite:
        return {"success": False, "message": "Zerodha credentials missing or invalid", "updated_count": 0}

    quote_symbols = []
    trade_symbol_map: Dict[str, List[Dict[str, Any]]] = {}
    for trade in open_trades:
        try:
            quote_symbol = _quote_symbol(trade.get("symbol"), trade.get("index"))
            quote_symbols.append(quote_symbol)
            trade_symbol_map.setdefault(quote_symbol, []).append(trade)
        except Exception:
            continue

    async def _retry_ltp(symbols: List[str]) -> Dict[str, Any]:
        delays = [0.2, 0.5, 1.0, 1.5, 2.0]
        for attempt, delay in enumerate(delays, 1):
            try:
                return kite.ltp(symbols)
            except Exception:
                if attempt == len(delays):
                    raise
                await asyncio.sleep(delay)

    async def _retry_quote(symbols: List[str]) -> Dict[str, Any]:
        delays = [0.2, 0.5, 1.0]
        for attempt, delay in enumerate(delays, 1):
            try:
                return kite.quote(symbols)
            except Exception:
                if attempt == len(delays):
                    raise
                await asyncio.sleep(delay)

    start = time.time()
    try:
        quotes = await _retry_ltp(quote_symbols)
    except Exception as e:
        live_update_state["failure_count"] += 1
        backoff = min(12.0, 4.0 + live_update_state["failure_count"] * 2.0)
        live_update_state["backoff_until"] = time.time() + backoff
        return {
            "success": False,
            "message": f"Failed to fetch prices: {str(e)}",
            "updated_count": 0,
            "retry_after": round(backoff, 2),
        }
    finally:
        live_update_state["last_duration"] = time.time() - start

    updated_count = 0
    missing_symbols: List[str] = []
    for quote_symbol, trades in trade_symbol_map.items():
        data = quotes.get(quote_symbol) or {}
        live_price = data.get("last_price")
        if live_price is None:
            missing_symbols.append(quote_symbol)
            continue
        new_price = float(live_price)
        live_price_cache[quote_symbol] = new_price
        for trade in trades:
            trade["current_price"] = new_price
            if _option_kind(trade.get("symbol")):
                entry = float(trade.get("price") or 0)
                if entry > 0:
                    profit_points = new_price - entry
                    if profit_points >= TRAIL_START_POINTS:
                        trail_stop = new_price - TRAIL_GAP_POINTS
                        current_sl = trade.get("stop_loss")
                        if current_sl is None or trail_stop > current_sl:
                            trade["stop_loss"] = round(trail_stop, 2)
            updated_count += 1

    if missing_symbols:
        try:
            fallback_quotes = await _retry_quote(missing_symbols)
        except Exception:
            fallback_quotes = {}
        for quote_symbol in missing_symbols:
            data = fallback_quotes.get(quote_symbol) or {}
            live_price = data.get("last_price")
            if live_price is None:
                cached = live_price_cache.get(quote_symbol)
                if cached is None:
                    continue
                live_price = cached
            new_price = float(live_price)
            live_price_cache[quote_symbol] = new_price
            for trade in trade_symbol_map.get(quote_symbol, []):
                trade["current_price"] = new_price
                if _option_kind(trade.get("symbol")):
                    entry = float(trade.get("price") or 0)
                    if entry > 0:
                        profit_points = new_price - entry
                        if profit_points >= TRAIL_START_POINTS:
                            trail_stop = new_price - TRAIL_GAP_POINTS
                            current_sl = trade.get("stop_loss")
                            if current_sl is None or trail_stop > current_sl:
                                trade["stop_loss"] = round(trail_stop, 2)
                updated_count += 1

    if live_update_state["last_duration"] > 2.5:
        live_update_state["failure_count"] += 1
        backoff = min(10.0, 3.0 + live_update_state["failure_count"])
        live_update_state["backoff_until"] = time.time() + backoff
    else:
        live_update_state["failure_count"] = 0

    return {
        "success": True,
        "updated_count": updated_count,
        "missing_symbols": missing_symbols,
        "duration": round(live_update_state["last_duration"], 2),
    }


@router.post("/trades/close")
async def close_active_trade(
    req: CloseTradeRequest,
    authorization: Optional[str] = Header(None),
):
    if not active_trades:
        raise HTTPException(status_code=404, detail="No active trades to close")

    trade = None
    if req.trade_id is not None:
        trade = next((t for t in active_trades if t.get("id") == req.trade_id and t.get("status") == "OPEN"), None)
    if trade is None and req.symbol:
        trade = next((t for t in active_trades if t.get("symbol") == req.symbol and t.get("status") == "OPEN"), None)

    if trade is None:
        raise HTTPException(status_code=404, detail="Active trade not found")

    symbol = trade.get("symbol")
    qty = int(trade.get("quantity") or 0)
    side = (trade.get("side") or "BUY").upper()
    exit_side = "SELL" if side == "BUY" else "BUY"
    exchange = trade.get("exchange") or "NFO"
    product = trade.get("product") or "MIS"
    exit_price = trade.get("current_price") or trade.get("price") or 0.0

    if not symbol or qty <= 0:
        raise HTTPException(status_code=400, detail="Invalid trade data")

    exit_order = place_zerodha_order(
        symbol=symbol,
        quantity=qty,
        side=exit_side,
        order_type="MARKET",
        product=product,
        exchange=exchange,
    )

    if not exit_order.get("success"):
        raise HTTPException(status_code=502, detail=exit_order.get("error") or "Exit order failed")

    trade["exit_reason"] = "MANUAL_CLOSE"
    trade["exit_order_id"] = exit_order.get("order_id")
    _close_trade(trade, exit_price)
    active_trades[:] = [t for t in active_trades if t.get("status") == "OPEN"]

    return {"success": True, "message": "Trade closed", "trade": trade}


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
            exit_reason = _should_exit_by_currency(trade, price)
            if exit_reason:
                trade["exit_reason"] = exit_reason
                _close_trade(trade, price)
                to_close.append(trade)
                closed += 1
                continue
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
    """Return LIVE market indices from Zerodha (real broker connected)."""
    print("\n[API /market/indices] Called - fetching LIVE data from Zerodha...")
    trends = await trend_analyzer.get_market_trends()
    indices = trends.get("indices", {}) if trends else {}
    
    if not indices:
        print("[API /market/indices] ⚠ WARNING: No indices data - broker may not be connected!")
    else:
        print(f"[API /market/indices] ✓ Got indices: {list(indices.keys())}")
    
    payload = [
        {
            "symbol": sym, 
            "price": data.get("current"), 
            "change_pct": data.get("change_percent"),
            "trend": data.get("trend"),
            "source": "zerodha_live"
        }
        for sym, data in indices.items()
    ]
    
    response = {
        "indices": payload,
        "timestamp": _now(),
        "count": len(payload),
        "source": "zerodha" if payload else "none"
    }
    print(f"[API /market/indices] ✓ Response: indices={len(payload)}, timestamp={response['timestamp']}")
    return response


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

@router.post("/run-strategy")
async def run_strategy(market_data: dict, credentials: dict, authorization: Optional[str] = Header(None)):
    # Connect broker
    if not engine.connect_broker("zerodha", credentials):
        return {"success": False, "error": "Failed to connect to Zerodha broker"}
    # Strategy pipeline
    opportunities = strategy.scan(market_data)
    signals = strategy.identify(opportunities)
    analyzed = strategy.analyze(signals)
    results = strategy.execute(analyzed, engine)
    engine.disconnect_broker("zerodha")
    return {"success": True, "results": results}
