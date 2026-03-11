import asyncio
from fastapi import APIRouter, Body, Header, HTTPException, BackgroundTasks, Query, Request
from pydantic import BaseModel
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
                trade["status"] = "SL_HIT"
                trade["exit_reason"] = "SL_HIT"
                _close_trade(trade, price)
        # Remove closed trades from active_trades
        active_trades[:] = [t for t in active_trades if t.get("status") == "OPEN"]

# Start background task on startup
@router.on_event("startup")
async def start_auto_close_trades():
    asyncio.create_task(auto_close_trades_task())
"""Auto Trading Engine wired to live market data (no mocks)."""

import math
import time
import asyncio
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dt_time
from typing import Any, Dict, List, Optional, Tuple



from fastapi import APIRouter, Body, Header, HTTPException
from app.routes.option_chain_utils import get_option_chain

from app.strategies.ai_model import ai_model
from app.strategies.market_intelligence import trend_analyzer
from app.engine.option_signal_generator import generate_signals, select_best_signal, _get_kite
from app.engine.paper_trade_updater import _quote_symbol
from app.core.database import SessionLocal
from app.models.trading import TradeReport
from sqlalchemy import func
from app.engine.auto_trading_engine import AutoTradingEngine
from app.engine.zerodha_broker import ZerodhaBroker
from app.models.auth import BrokerCredential
from app.engine.simple_momentum_strategy import SimpleMomentumStrategy
from app.core.market_hours import ist_now, is_market_open, market_status
from app.routes.trade_metrics import normalize_active_trade_metrics
from app.routes.signal_scoring import evaluate_advanced_ai_signal
from app.engine.zerodha_order_util import place_zerodha_order


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

MAX_TRADES = 3  # allow up to 3 concurrent trades
SINGLE_ACTIVE_TRADE = False  # permit multiple live trades concurrently
EMERGENCY_STOP_MULTIPLIER = 0.9  # Trigger protective exits slightly before hard SL.
TARGET_PCT = 0.6  # target move in percent (slightly above stop for RR >= 1)
STOP_PCT = 0.4    # stop move in percent (tighter risk)
STOP_PCT_OPTIONS = 4.0  # option premium SL distance in percent
TARGET_POINTS = 25.0  # fixed option target points for fast intraday exits
MAX_STOP_POINTS = 20.0  # hard cap on stop distance in points
PROFIT_EXIT_AMOUNT = 500.0  # lock profit once this PnL is achieved
LOSS_CAP_AMOUNT = 600.0  # emergency per-trade currency loss cap
CONFIRM_MOMENTUM_PCT = 0.1  # very loose confirmation so signals appear on small moves
MIN_WIN_RATE = 0.6          # suppress signals if recent hit-rate is below this
MIN_WIN_SAMPLE = 8          # minimum closed trades before applying win-rate gate

# Risk controls (can be made configurable later)
risk_config = {
    "max_daily_loss": 5000.0,        # ₹5000 max daily loss (hardstop to protect capital)
    "max_daily_profit": 10000.0,     # ₹10000 daily profit target (auto-stop at profit)
    "max_per_trade_loss": 600.0,     # ₹600 max loss per trade (prevent single trade disaster)
    "max_consecutive_losses": 0,     # NO consecutive loss limit - immediate loss checking
    "max_position_pct": 0.10,        # 10% max per position
    "max_portfolio_pct": 0.10,       # 10% total exposure
    "cooldown_minutes": 0,           # NO COOLDOWN - trade immediately if conditions met
    "symbol_cooldown_minutes": 2,    # Cooldown after SL on same symbol/root
    "min_momentum_pct": 0.5,         # Very strong momentum (0.5%) - avoid weak entries
    "min_trend_strength": 0.8,       # HIGH trend strength (80%) required - quality only
    "require_trend_confirmation": True,  # STRICT: Confirm trend before entry
    "min_win_rate_threshold": 0.70,  # Only trade if win rate > 70%
    "avoid_high_volatility": True,   # Skip trades in extremely volatile markets
    "dynamic_loss_brake": True,      # Tighten entry rules as drawdown/loss streak rises
    "loss_brake_drawdown_start": 0.35,  # Start tightening after 35% of daily loss limit
    "loss_brake_drawdown_hard": 0.80,   # Hard brake near 80% of daily loss limit
    "loss_brake_loss_streak_start": 1,  # Tighten after first consecutive losing trade
    "loss_brake_loss_streak_hard": 3,   # Hard brake after 3 consecutive losses
    "loss_brake_hard_block": True,      # Block new entries in hard-brake state
    "loss_brake_qty_warn": 0.75,        # Reduce quantity to 75% in warning state
    "loss_brake_qty_hard": 0.50,        # Reduce quantity to 50% in hard state
    "capital_protection_mode": True,    # Enforce strict profile-based capital safeguards
    "capital_daily_loss_pct": 0.01,     # Stop new entries after 1% daily drawdown on account balance
    "capital_per_trade_risk_pct": 0.003,  # Per-trade max risk: 0.3% of balance
    "capital_position_pct": 0.03,       # Max 3% of balance in a single new position
    "capital_portfolio_pct": 0.06,      # Max 6% total live exposure
    "capital_min_balance": 5000.0,      # Do not place live trades below this balance
    "live_start_balance_only": True,    # For live mode, require balance availability as an additional prerequisite
    "allow_simultaneous_live_trades": True,  # Permit concurrent live trades when setup is strong
    "max_simultaneous_live_trades": 3,
    "max_simultaneous_live_trades": 3,       # Hard cap for concurrent live trades
    "simultaneous_min_quality": 82.0,        # Additional trade requires solid quality
    "simultaneous_min_confidence": 72.0,     # Additional trade requires healthy confidence
    "simultaneous_min_ai_edge": 40.0,        # Additional trade requires minimum positive AI edge
    "simultaneous_require_different_root": True,  # Second trade must be on different underlying/root
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

# ATR-based stop configuration
atr_config = {
    "enabled": True,
    "period": 14,
    # Multiplier applied to ATR for initial stop (in underlying points)
    "multiplier": 1.0,
    # For options we scale the underlying ATR to a conservative premium movement
    "option_scale": 0.45,
    # Minimum candles to compute ATR
    "min_candles": 5,
}

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

# Auto-scan background worker state
auto_scan_task: Optional[asyncio.Task] = None
auto_scan_state: Dict[str, Any] = {
    "running": False,
    "interval": 3,
    "symbols": ["NIFTY", "BANKNIFTY"],
    "instrument_type": "weekly_option",
    "balance": 50000.0,
    "last_run": None,
    "last_recommendation": None,
}

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
    return ist_now().isoformat()


def _live_protection_active() -> bool:
    """Apply strict protections only when live trading is armed and not in demo mode."""
    return bool(state.get("live_armed", True)) and not bool(state.get("is_demo_mode", False))


def _has_live_balance_for_trade(balance: float, capital_required: float) -> bool:
    """Live-mode start gate: allow trade when available balance can fund it."""
    bal = max(0.0, float(balance or 0.0))
    req = max(0.0, float(capital_required or 0.0))
    in_use = max(0.0, float(_capital_in_use() or 0.0))
    return req > 0 and (in_use + req) <= bal


def _can_allow_additional_live_trade(candidate: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Allow concurrent live trade only for ultra-high-quality, diversified signals."""
    open_trades = [t for t in active_trades if t.get("status") == "OPEN"]
    if not open_trades:
        return True, []

    if not _live_protection_active():
        return True, []

    reasons: List[str] = []
    if not bool(risk_config.get("allow_simultaneous_live_trades", False)):
        reasons.append("single_trade_lock")
        return False, reasons

    max_concurrent = max(1, int(risk_config.get("max_simultaneous_live_trades") or 1))
    if len(open_trades) >= max_concurrent:
        reasons.append(f"max_simultaneous_reached({len(open_trades)}>={max_concurrent})")
        return False, reasons

    if not isinstance(candidate, dict):
        reasons.append("missing_candidate_context")
        return False, reasons

    quality = float(candidate.get("quality_score") or candidate.get("quality") or 0.0)
    confidence = float(candidate.get("confirmation_score") or candidate.get("confidence") or 0.0)
    ai_edge = float(candidate.get("ai_edge_score") or 0.0)

    q_min = float(risk_config.get("simultaneous_min_quality") or 82.0)
    c_min = float(risk_config.get("simultaneous_min_confidence") or 72.0)
    e_min = float(risk_config.get("simultaneous_min_ai_edge") or 40.0)

    if quality < q_min:
        reasons.append(f"quality<{q_min:.1f} ({quality:.1f})")
    if confidence < c_min:
        reasons.append(f"confidence<{c_min:.1f} ({confidence:.1f})")
    if ai_edge < e_min:
        reasons.append(f"ai_edge<{e_min:.1f} ({ai_edge:.1f})")

    if bool(risk_config.get("simultaneous_require_different_root", True)):
        cand_root = _symbol_root(str(candidate.get("symbol") or ""))
        if cand_root:
            open_roots = {
                _symbol_root(str(t.get("symbol") or ""))
                for t in open_trades
                if _symbol_root(str(t.get("symbol") or ""))
            }
            if cand_root in open_roots:
                reasons.append(f"same_root_blocked({cand_root})")

    return len(reasons) == 0, reasons


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


def _cooldown_keys_for_trade(symbol: str | None, side: str | None) -> List[str]:
    root = _symbol_root(symbol)
    kind = _option_kind(symbol) or "NA"
    norm_side = (side or "BUY").upper()
    keys: List[str] = []
    if root:
        keys.append(f"{root}:{norm_side}")
        keys.append(f"{root}:{kind}:{norm_side}")
    if symbol:
        keys.append(f"{symbol.upper()}:{norm_side}")
    return keys


def _record_sl_cooldown(symbol: str | None, side: str | None, at: Optional[datetime] = None) -> None:
    at = at or datetime.utcnow()
    cooldowns = state.setdefault("symbol_cooldowns", {})
    expiry = at + timedelta(minutes=int(risk_config.get("symbol_cooldown_minutes", 2) or 2))
    for key in _cooldown_keys_for_trade(symbol, side):
        cooldowns[key] = {
            "reason": "SL_HIT",
            "expires_at": expiry.isoformat(),
            "symbol": symbol,
            "side": (side or "BUY").upper(),
        }


def _cooldown_info(symbol: str | None, side: str | None) -> Tuple[bool, float, Optional[str]]:
    now = datetime.utcnow()
    cooldowns = state.setdefault("symbol_cooldowns", {})
    active_remaining = 0.0
    hit_key: Optional[str] = None
    stale_keys: List[str] = []

    for key in _cooldown_keys_for_trade(symbol, side):
        rec = cooldowns.get(key)
        if not rec:
            continue
        expires_at_raw = rec.get("expires_at")
        if not expires_at_raw:
            stale_keys.append(key)
            continue
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except Exception:
            stale_keys.append(key)
            continue

        remaining = (expires_at - now).total_seconds()
        if remaining > 0:
            if remaining > active_remaining:
                active_remaining = remaining
                hit_key = key
        else:
            stale_keys.append(key)

    for key in stale_keys:
        cooldowns.pop(key, None)

    return active_remaining > 0, max(0.0, active_remaining), hit_key


def _compute_rr(entry_price: Any, target: Any, stop_loss: Any) -> float:
    try:
        entry = float(entry_price or 0)
        tgt = float(target or 0)
        sl = float(stop_loss or 0)
        risk = abs(entry - sl)
        reward = abs(tgt - entry)
        return (reward / risk) if risk > 0 else 0.0
    except Exception:
        return 0.0


def _ai_entry_validation(
    signal: Dict[str, Any],
    loss_brake: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Server-side AI gate: quality + confidence + RR + trend/technical alignment."""
    reasons: List[str] = []

    quality = float(signal.get("quality_score") or signal.get("quality") or 0)
    confidence = float(signal.get("confirmation_score") or signal.get("confidence") or 0)
    rr = _compute_rr(signal.get("entry_price"), signal.get("target"), signal.get("stop_loss"))
    market_regime = str(signal.get("market_regime") or "").upper()

    quality_min = 70.0
    confidence_min = 70.0
    rr_min = 1.1
    if isinstance(loss_brake, dict) and loss_brake.get("enabled"):
        quality_min += float(loss_brake.get("quality_boost") or 0)
        confidence_min += float(loss_brake.get("confidence_boost") or 0)
        rr_min += float(loss_brake.get("rr_boost") or 0)
        if loss_brake.get("block_new_entries"):
            reasons.append("loss_brake_hard_block")

    if quality < quality_min:
        reasons.append(f"quality<{quality_min:.1f} ({quality:.1f})")
    if confidence < confidence_min:
        reasons.append(f"confidence<{confidence_min:.1f} ({confidence:.1f})")
    if rr < rr_min:
        reasons.append(f"rr<{rr_min:.2f} ({rr:.2f})")

    option_type = str(signal.get("option_type") or "").upper()
    trend_direction = str(signal.get("trend_direction") or "").upper()
    if trend_direction and option_type in {"CE", "PE"}:
        trend_ok = (
            ("UP" in trend_direction and option_type == "CE")
            or ("DOWN" in trend_direction and option_type == "PE")
        )
        if not trend_ok:
            reasons.append(f"trend_mismatch({trend_direction}->{option_type})")

    tech = signal.get("technical_indicators") or {}
    if isinstance(tech, dict) and option_type in {"CE", "PE"}:
        rsi = float(tech.get("rsi") or 50)
        macd = tech.get("macd") if isinstance(tech.get("macd"), dict) else {}
        macd_cross = str(macd.get("crossover") or "").lower()

        if option_type == "CE":
            tech_ok = (45 <= rsi <= 75) and (macd_cross in {"", "bullish"})
        else:
            tech_ok = (25 <= rsi <= 55) and (macd_cross in {"", "bearish"})

        if not tech_ok:
            reasons.append(f"technical_mismatch(rsi={rsi:.1f},macd={macd_cross or 'na'})")

    base_reason_count = len(reasons)
    advanced = evaluate_advanced_ai_signal(signal)
    advanced["loss_brake"] = loss_brake or {"enabled": False, "stage": "OFF"}
    advanced["thresholds"] = {
        "quality_min": round(quality_min, 2),
        "confidence_min": round(confidence_min, 2),
        "rr_min": round(rr_min, 2),
    }
    if not advanced.get("entry_valid", False):
        advanced_reasons = [str(r) for r in (advanced.get("entry_reasons") or [])]
        soft_advanced_reasons = {"low_momentum", "low_ai_edge_score"}
        
        # Two pathways for override:
        # 1) High conviction with ONLY soft reasons (safer path)
        # 2) Ultra-high conviction even with mixed reasons (aggressive path for excellent trades)
        has_only_soft = set(advanced_reasons).issubset(soft_advanced_reasons) if advanced_reasons else False
        
        # Ultra-high conviction: quality>=94, confidence>=90, RR>=1.25 (excellent setup)
        ultra_high_conviction = (
            quality >= 94.0 and 
            confidence >= 90.0 and 
            rr >= 1.25
        )
        
        high_conviction_soft_override = (
            len(reasons) == base_reason_count
            and quality >= 90.0
            and confidence >= 85.0
            and rr >= 1.20
            and bool(advanced_reasons)
            and (
                (has_only_soft and market_regime != "LOW_VOLATILITY")
                or ultra_high_conviction
            )
        )

        if high_conviction_soft_override:
            advanced["entry_valid"] = True
            advanced["override_applied"] = "HIGH_CONVICTION_SOFT_AI_GATE" if has_only_soft else "ULTRA_HIGH_CONVICTION_AI_GATE"
        else:
            reasons.extend([f"advanced:{r}" for r in advanced_reasons])

    # Premium movement check
    if market_regime == "LOW_VOLATILITY":
        reasons.append("premium_movement_slow")

    return len(reasons) == 0, reasons, advanced


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


def _entry_timing_risk_profile(now_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """Return quantity multiplier during volatile windows (open/close/event)."""
    dt = now_dt or ist_now()
    t = dt.time()

    # High-noise windows: opening minutes, pre-close, and a midday event-risk window.
    open_volatile = dt_time(9, 15) <= t <= dt_time(9, 35)
    close_volatile = dt_time(14, 55) <= t <= dt_time(15, 30)
    event_volatile = dt_time(12, 25) <= t <= dt_time(12, 35)

    if open_volatile:
        return {"volatile": True, "window": "OPENING", "qty_multiplier": 0.7}
    if close_volatile:
        return {"volatile": True, "window": "PRE_CLOSE", "qty_multiplier": 0.7}
    if event_volatile:
        return {"volatile": True, "window": "EVENT_WINDOW", "qty_multiplier": 0.8}
    return {"volatile": False, "window": "NORMAL", "qty_multiplier": 1.0}


def _loss_brake_profile() -> Dict[str, Any]:
    """Adaptive risk brake using intraday drawdown and loss streak."""
    if not risk_config.get("dynamic_loss_brake", False):
        return {
            "enabled": False,
            "stage": "OFF",
            "drawdown_ratio": 0.0,
            "consecutive_losses": int(state.get("consecutive_losses") or 0),
            "quality_boost": 0,
            "confidence_boost": 0,
            "rr_boost": 0.0,
            "qty_multiplier": 1.0,
            "block_new_entries": False,
        }

    max_daily_loss = float(risk_config.get("max_daily_loss") or 0.0)
    daily_loss = float(state.get("daily_loss") or 0.0)
    consecutive_losses = int(state.get("consecutive_losses") or 0)
    drawdown_ratio = (daily_loss / max_daily_loss) if max_daily_loss > 0 else 0.0

    drawdown_start = float(risk_config.get("loss_brake_drawdown_start") or 0.35)
    drawdown_hard = float(risk_config.get("loss_brake_drawdown_hard") or 0.80)
    streak_start = int(risk_config.get("loss_brake_loss_streak_start") or 1)
    streak_hard = int(risk_config.get("loss_brake_loss_streak_hard") or 3)

    warn = (drawdown_ratio >= drawdown_start) or (consecutive_losses >= streak_start)
    hard = (drawdown_ratio >= drawdown_hard) or (consecutive_losses >= streak_hard)

    if hard:
        stage = "HARD"
        quality_boost = 8
        confidence_boost = 8
        rr_boost = 0.25
        qty_multiplier = float(risk_config.get("loss_brake_qty_hard") or 0.50)
        block_new_entries = bool(risk_config.get("loss_brake_hard_block", True))
    elif warn:
        stage = "WARN"
        quality_boost = 4
        confidence_boost = 4
        rr_boost = 0.15
        qty_multiplier = float(risk_config.get("loss_brake_qty_warn") or 0.75)
        block_new_entries = False
    else:
        stage = "NORMAL"
        quality_boost = 0
        confidence_boost = 0
        rr_boost = 0.0
        qty_multiplier = 1.0
        block_new_entries = False

    return {
        "enabled": True,
        "stage": stage,
        "drawdown_ratio": round(drawdown_ratio, 4),
        "consecutive_losses": consecutive_losses,
        "quality_boost": quality_boost,
        "confidence_boost": confidence_boost,
        "rr_boost": rr_boost,
        "qty_multiplier": max(0.1, min(1.0, qty_multiplier)),
        "block_new_entries": block_new_entries,
    }


def _capital_protection_profile(balance: float) -> Dict[str, Any]:
    """Build strict capital-guard limits from current account balance."""
    bal = max(0.0, float(balance or 0.0))
    enabled = bool(risk_config.get("capital_protection_mode", True))

    daily_loss_pct = float(risk_config.get("capital_daily_loss_pct") or 0.01)
    per_trade_risk_pct = float(risk_config.get("capital_per_trade_risk_pct") or 0.003)
    position_pct = float(risk_config.get("capital_position_pct") or 0.03)
    portfolio_pct = float(risk_config.get("capital_portfolio_pct") or 0.06)
    min_balance = float(risk_config.get("capital_min_balance") or 0.0)

    daily_loss_cap = min(float(risk_config.get("max_daily_loss") or 0.0), bal * daily_loss_pct) if bal > 0 else 0.0
    per_trade_loss_cap = min(float(risk_config.get("max_per_trade_loss") or 0.0), bal * per_trade_risk_pct) if bal > 0 else 0.0

    return {
        "enabled": enabled,
        "profile": "CAPITAL_SHIELD_100",
        "balance": round(bal, 2),
        "min_balance": round(min_balance, 2),
        "daily_loss_cap": round(max(0.0, daily_loss_cap), 2),
        "per_trade_loss_cap": round(max(0.0, per_trade_loss_cap), 2),
        "max_position_cap": round(max(0.0, bal * position_pct), 2),
        "max_portfolio_cap": round(max(0.0, bal * portfolio_pct), 2),
        "daily_loss_pct": daily_loss_pct,
        "per_trade_risk_pct": per_trade_risk_pct,
        "position_pct": position_pct,
        "portfolio_pct": portfolio_pct,
    }


def _capital_guard_reasons(
    profile: Dict[str, Any],
    capital_required: float,
    potential_loss: float,
    capital_in_use: float,
) -> List[str]:
    """Return blocking reasons for new trade entry under strict capital protection."""
    reasons: List[str] = []
    if not profile.get("enabled"):
        return reasons

    balance = float(profile.get("balance") or 0.0)
    min_balance = float(profile.get("min_balance") or 0.0)
    if balance < min_balance:
        reasons.append(f"balance_below_min({balance:.2f}<{min_balance:.2f})")

    daily_loss_cap = float(profile.get("daily_loss_cap") or 0.0)
    day_loss = float(state.get("daily_loss") or 0.0)
    if daily_loss_cap > 0 and day_loss >= daily_loss_cap:
        reasons.append(f"daily_loss_cap_reached({day_loss:.2f}>={daily_loss_cap:.2f})")

    per_trade_loss_cap = float(profile.get("per_trade_loss_cap") or 0.0)
    if per_trade_loss_cap > 0 and potential_loss > per_trade_loss_cap:
        reasons.append(f"per_trade_risk_exceeded({potential_loss:.2f}>{per_trade_loss_cap:.2f})")

    max_position_cap = float(profile.get("max_position_cap") or 0.0)
    if max_position_cap > 0 and capital_required > max_position_cap:
        reasons.append(f"position_cap_exceeded({capital_required:.2f}>{max_position_cap:.2f})")

    max_portfolio_cap = float(profile.get("max_portfolio_cap") or 0.0)
    total_after = float(capital_in_use or 0.0) + float(capital_required or 0.0)
    if max_portfolio_cap > 0 and total_after > max_portfolio_cap:
        reasons.append(f"portfolio_cap_exceeded({total_after:.2f}>{max_portfolio_cap:.2f})")

    return reasons


def _apply_qty_multiplier(base_qty: int, lot_step: int, multiplier: float) -> int:
    if base_qty <= 0:
        return base_qty
    if multiplier >= 0.999:
        return base_qty
    step = max(1, lot_step)
    # Keep at least one lot and preserve lot-step divisibility.
    reduced = max(step, int(base_qty * multiplier))
    reduced = (reduced // step) * step
    return max(step, reduced)


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


def _extract_underlying_symbol(raw_symbol: Optional[str]) -> str:
    symbol = str(raw_symbol or "").upper()
    if not symbol:
        return "NIFTY"
    aliases = ["BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTY"]
    for name in aliases:
        if name in symbol:
            return name
    # Handle "NIFTY INDEX" style labels.
    if " INDEX" in symbol:
        return symbol.replace(" INDEX", "").strip()
    return symbol.split()[0]


def _yahoo_ticker_for_underlying(underlying: str) -> str:
    mapping = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
        "SENSEX": "^BSESN",
        "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
    }
    return mapping.get(underlying, "^NSEI")


def _fetch_recent_candles(underlying: str, candle_count: int = 5) -> List[Dict[str, float]]:
    try:
        import yfinance as yf

        ticker = yf.Ticker(_yahoo_ticker_for_underlying(underlying))
        df = ticker.history(period="2d", interval="5m")
        if df.empty:
            return []
        rows = []
        for _, row in df.tail(max(3, candle_count)).iterrows():
            rows.append({
                "open": float(row.get("Open") or 0),
                "high": float(row.get("High") or 0),
                "low": float(row.get("Low") or 0),
                "close": float(row.get("Close") or 0),
            })
        return rows
    except Exception as e:
        print(f"[CANDLE FETCH ERROR] {underlying}: {e}")
        return []


def _require_multi_tick_confirmation(underlying: str, entry_price: float, side: str, required_ticks: int = 3) -> bool:
    """Return True if the last `required_ticks` closes confirm the entry direction.

    For BUY we require closes >= entry_price for each recent candle.
    For SELL we require closes <= entry_price for each recent candle.
    This is a conservative server-side guard to avoid impulsive entries.
    """
    try:
        candles = _fetch_recent_candles(underlying, candle_count=required_ticks)
        if not candles or len(candles) < required_ticks:
            return False
        closes = [float(c.get('close', 0)) for c in candles[-required_ticks:]]
        if side.upper() == 'BUY':
            return all(c >= entry_price for c in closes)
        else:
            return all(c <= entry_price for c in closes)
    except Exception:
        return False


@router.post("/toggle")
async def toggle(enabled: bool = True, authorization: Optional[str] = Header(None)):
    # Auto-trading is always enabled; respond with enabled state for UI compatibility.
    return {"enabled": True, "is_demo_mode": state["is_demo_mode"], "message": "Auto-trading is always enabled."}


def _init_trailing_fields(entry_price: float, side: str) -> Dict[str, float | bool]:
    # Precompute trailing stop anchor to avoid repeated math and simplify updates.
    buffer = trail_config["buffer_pct"] * entry_price / 100
    if side == "BUY":
        # Activate trail only after favorable move above entry.
        start = entry_price * (1 + trail_config["trigger_pct"] / 100)
        return {
            "trail_active": False,
            "trail_start": start,
            "trail_stop": start - buffer,
            "trail_step": trail_config["step_pct"] * entry_price / 100,
        }
    # For SELL, favorable move is below entry.
    start = entry_price * (1 - trail_config["trigger_pct"] / 100)
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

    # Self-heal legacy anchors from older logic so existing open trades trail correctly.
    if side == "BUY" and trail_start < entry_price:
        repaired = _init_trailing_fields(float(entry_price), side)
        trade.update(repaired)
        trail_start = trade.get("trail_start")
        trail_stop = trade.get("trail_stop")
        trail_step = trade.get("trail_step")
    elif side != "BUY" and trail_start > entry_price:
        repaired = _init_trailing_fields(float(entry_price), side)
        trade.update(repaired)
        trail_start = trade.get("trail_start")
        trail_stop = trade.get("trail_stop")
        trail_step = trade.get("trail_step")

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

    # Strong one-way trailing: BUY stop can only move up; SELL stop can only move down.
    prev_trail_stop = float(trade.get("trail_stop") or trail_stop)

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
                # One-way lock: never loosen BUY trail.
                trail_stop = max(float(trail_stop), prev_trail_stop)
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
                # One-way lock: never loosen SELL trail.
                trail_stop = min(float(trail_stop), prev_trail_stop)
                trade["trail_start"] = trail_start
                trade["trail_stop"] = trail_stop


def _close_trade(trade: Dict[str, Any], exit_price: float) -> None:
    """Close an open trade: compute P&L, update state, record cooldowns and persist to DB."""
    try:
        side = (trade.get("side") or "BUY").upper()
        qty = int(trade.get("quantity") or 0)
        entry = float(trade.get("price") or trade.get("entry_price") or 0.0)
        exit_price = float(exit_price or trade.get("current_price") or entry)

        pnl = _pnl_for_trade(trade, exit_price)
        capital = float(trade.get("capital_used") or (entry * qty) or 0.0)
        pnl_percentage = (pnl / capital * 100) if capital else 0.0

        trade["exit_price"] = exit_price
        trade["exit_time"] = _now()
        trade["status"] = trade.get("status") or "CLOSED"
        trade["pnl"] = round(pnl, 2)
        trade["pnl_percentage"] = round(pnl_percentage, 2)

        # Record SL cooldown and append to history
        exit_dt = datetime.fromisoformat(trade.get("exit_time")) if isinstance(trade.get("exit_time"), str) else datetime.utcnow()
        _record_sl_cooldown(trade.get("symbol") or trade.get("index"), side, exit_dt)
        history.append(trade.copy())

        # Track daily P&L and consecutive losses
        state["daily_loss"] += pnl
        state["daily_profit"] = state.get("daily_profit", 0.0) + max(0, pnl)
        if pnl < 0:
            state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
            state["last_loss_time"] = datetime.now()
        else:
            state["consecutive_losses"] = 0

        print(f"\n[TRADE CLOSED] P&L: ₹{pnl:.2f}")
        print(f"  Daily Loss: ₹{state['daily_loss']:.2f} / ₹{risk_config['max_daily_loss']}")
        print(f"  Daily Profit: ₹{state['daily_profit']:.2f} / ₹{risk_config['max_daily_profit']}")

        # Persist closed trade to database for reporting
        try:
            db = SessionLocal()
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
    except Exception as e:
        print(f"[CLOSE TRADE ERROR] {e}")


def _maybe_place_exit_order(trade: Dict[str, any], exit_price: float) -> None:
    """Attempt to place a market exit order for live trades (no-op in demo)."""
    try:
        if state.get("is_demo_mode", False):
            return
        symbol = trade.get("symbol")
        qty = int(trade.get("quantity") or 0)
        side = (trade.get("side") or "BUY").upper()
        if not symbol or qty <= 0:
            return
        exit_side = "SELL" if side == "BUY" else "BUY"
        exchange = trade.get("exchange") or "NFO"
        product = trade.get("product") or "MIS"
        resp = place_zerodha_order(symbol=symbol, quantity=qty, side=exit_side, order_type="MARKET", product=product, exchange=exchange)
        if resp.get("success"):
            trade["exit_order_id"] = resp.get("order_id")
        else:
            trade["exit_error"] = resp.get("error")
    except Exception as e:
        trade["exit_error"] = str(e)


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


async def _auto_scan_worker():
    """Background worker that calls `analyze` periodically and attempts to start trades when a start signal appears."""
    global auto_scan_state
    while auto_scan_state.get("running"):
        try:
            interval = float(auto_scan_state.get("interval") or 3)
            symbols = auto_scan_state.get("symbols") or ["NIFTY", "BANKNIFTY"]
            instrument_type = auto_scan_state.get("instrument_type") or "weekly_option"
            balance = float(auto_scan_state.get("balance") or 50000.0)

            auto_scan_state["last_run"] = _now()
            # Call analyze with the configured symbols; it may auto-execute based on internal gates
            try:
                resp = await analyze(symbol=symbols[0], balance=balance, symbols=",".join(symbols), instrument_type=instrument_type, quantity=None)
            except Exception as e:
                resp = {"error": str(e)}

            auto_scan_state["last_recommendation"] = resp.get("recommendation") if isinstance(resp, dict) else None

            # If a recommendation exists and indicates start_trade_allowed, attempt execute
            rec = auto_scan_state["last_recommendation"]
            if rec and rec.get("start_trade_allowed"):
                try:
                    # Demo mode should be explicit; do not silently downgrade live to demo.
                    force_demo = bool(state.get("is_demo_mode", False))
                    if (not force_demo) and (not bool(state.get("live_armed", True))):
                        await asyncio.sleep(interval)
                        continue
                    await execute(
                        symbol=rec.get("symbol"),
                        price=float(rec.get("entry_price") or 0.0),
                        balance=balance,
                        quantity=int(rec.get("quantity") or 1),
                        side=rec.get("action") or "BUY",
                        stop_loss=rec.get("stop_loss"),
                        target=rec.get("target"),
                        force_demo=force_demo,
                    )
                    # After an executed trade, wait a bit longer to let positions settle
                    await asyncio.sleep(max(5, interval))
                except Exception as e:
                    print(f"[AUTO_SCAN] execute failed: {e}")

            await asyncio.sleep(interval)
        except Exception as e:
            print(f"[AUTO_SCAN] worker error: {e}")
            await asyncio.sleep(3)


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
    market = market_status(dt_time(9, 15), dt_time(15, 30))
    print("[DEBUG] /autotrade/status market_status:", market, flush=True)
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
        "market_open": market["is_open"],
        "market_reason": market["reason"],
        "market_date": market["current_date"],
        "market_time": market["current_time"],
        "timestamp": _now(),
    }
    print("[DEBUG] /autotrade/status payload:", payload, flush=True)
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
    allow_auto_execute: bool = True,
):
    # Block new analysis/trade discovery outside configured market window.
    if not _within_trade_window():
        market = market_status(dt_time(9, 15), dt_time(15, 30))
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Market is closed. New trades are blocked outside market hours.",
                "market_open": market.get("is_open", False),
                "market_reason": market.get("reason", "Market closed"),
                "current_time": market.get("current_time"),
            },
        )

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

    # Enrich each signal with underlying regime and last 3-5 candles for fake breakout detection.
    context_cache: Dict[str, Dict[str, Any]] = {}
    for sig in signals:
        underlying = _extract_underlying_symbol(sig.get("symbol") or sig.get("index"))
        cached = context_cache.get(underlying)
        if not cached:
            regime = _detect_market_regime(underlying)
            candles = _fetch_recent_candles(underlying, candle_count=5)
            cached = {
                "market_regime": str(regime.get("regime") or "UNKNOWN"),
                "market_regime_score": float(regime.get("score") or 0.0),
                "recent_candles": candles,
            }
            context_cache[underlying] = cached
        sig["market_regime"] = cached["market_regime"]
        sig["market_regime_score"] = cached["market_regime_score"]
        sig["recent_candles"] = cached["recent_candles"]

    # Build recommendations for all signals (including CE/PE ATM options)
    recommendations = []
    blocked_recommendations = []
    ai_rejected_recommendations = []
    protection_active = _live_protection_active()
    live_balance_only_mode = protection_active and bool(risk_config.get("live_start_balance_only", False))
    risk_profile = _entry_timing_risk_profile()
    loss_brake = _loss_brake_profile() if protection_active else {
        "enabled": False,
        "stage": "PAPER",
        "drawdown_ratio": 0.0,
        "consecutive_losses": int(state.get("consecutive_losses") or 0),
        "quality_boost": 0,
        "confidence_boost": 0,
        "rr_boost": 0.0,
        "qty_multiplier": 1.0,
        "block_new_entries": False,
    }
    for sig in signals:
        blocked, remaining_seconds, _ = _cooldown_info(sig.get("symbol"), sig.get("action"))
        ai_ok, ai_reasons, ai_diag = _ai_entry_validation(sig, loss_brake=loss_brake)
        if blocked:
            blocked_recommendations.append({
                "symbol": sig.get("symbol"),
                "side": (sig.get("action") or "BUY").upper(),
                "wait_seconds": round(remaining_seconds, 1),
                "reason": "SL_HIT_COOLDOWN",
            })
        if not ai_ok:
            ai_rejected_recommendations.append({
                "symbol": sig.get("symbol"),
                "side": (sig.get("action") or "BUY").upper(),
                "reason": "AI_QUALITY_GATE",
                "details": ai_reasons,
                "advanced": ai_diag,
            })
        base_qty = int(sig.get("quantity") or 1)
        lot_step = int(sig.get("quantity") or 1)
        timing_multiplier = float(risk_profile.get("qty_multiplier") or 1.0)
        loss_brake_multiplier = float(loss_brake.get("qty_multiplier") or 1.0)
        combined_qty_multiplier = max(0.1, min(1.0, timing_multiplier * loss_brake_multiplier))
        adjusted_qty = _apply_qty_multiplier(base_qty, lot_step, combined_qty_multiplier)
        capital_required = round(float(sig["entry_price"]) * adjusted_qty, 2)

        market_regime = ai_diag.get("market_regime") or sig.get("market_regime")
        premium_movement_ok = True
        premium_movement_detail = "Normal movement - OK"
        if market_regime == "HIGH_VOLATILITY":
            premium_movement_ok = True
            premium_movement_detail = "Fast moving - OK"
        elif market_regime == "LOW_VOLATILITY":
            premium_movement_ok = False
            premium_movement_detail = "Slow moving - Avoid"

        recommendations.append({
            "action": sig["action"],
            "symbol": sig["symbol"],
            "confidence": sig["confidence"],
            "confirmation_score": sig.get("confirmation_score"),
            "quality_score": sig.get("quality_score"),
            "strategy": sig["strategy"],
            "entry_price": sig["entry_price"],
            "stop_loss": sig["stop_loss"],
            "target": sig["target"],
            "quantity": adjusted_qty,
            "base_quantity": base_qty,
            "capital_required": capital_required,
            "potential_profit": round((sig["target"] - sig["entry_price"]) * adjusted_qty, 2),
            "risk": round((sig["entry_price"] - sig["stop_loss"]) * adjusted_qty, 2),
            "expiry": sig.get("expiry"),
            "expiry_date": sig.get("expiry_date"),
            "underlying_price": sig.get("underlying_price"),
            "target_points": sig.get("target_points"),
            "roi_percentage": round(((sig["target"] - sig["entry_price"]) * adjusted_qty / capital_required) * 100, 2) if capital_required else 0.0,
            "trail": {
                "enabled": trail_config["enabled"],
                "trigger_pct": trail_config["trigger_pct"],
                "step_pct": trail_config["step_pct"],
            },
            "option_type": sig.get("option_type"),
            "strike": sig.get("strike"),
            "trend_direction": sig.get("trend_direction"),
            "trend_strength": sig.get("trend_strength"),
            "technical_indicators": sig.get("technical_indicators"),
            "data_source": sig.get("data_source"),
            "option_chain": option_chains[0] if option_chains else None if sig == signals[0] else None,
            "blocked_by_cooldown": blocked,
            "cooldown_wait_seconds": round(remaining_seconds, 1) if blocked else 0,
            "ai_valid": ai_ok,
            "ai_reasons": ai_reasons,
            "trend_confirmed": ai_diag.get("trend_confirmed"),
            "momentum_confirmed": ai_diag.get("momentum_confirmed"),
            "breakout_confirmed": ai_diag.get("breakout_confirmed"),
            "regime_score": ai_diag.get("regime_score"),
            "momentum_score": ai_diag.get("momentum_score"),
            "breakout_score": ai_diag.get("breakout_score"),
            "fake_move_risk": ai_diag.get("fake_move_risk"),
            "sudden_news_risk": ai_diag.get("sudden_news_risk"),
            "liquidity_spike_risk": ai_diag.get("liquidity_spike_risk"),
            "premium_distortion_risk": ai_diag.get("premium_distortion_risk"),
            "ai_edge_score": ai_diag.get("ai_edge_score"),
            "rr_score": ai_diag.get("rr_score"),
            "market_regime": ai_diag.get("market_regime") or sig.get("market_regime"),
            "market_regime_score": sig.get("market_regime_score"),
            "thresholds": ai_diag.get("thresholds"),
            "close_back_in_range": ai_diag.get("close_back_in_range"),
            "fake_breakout_by_candle": ai_diag.get("fake_breakout_by_candle"),
            "breakout_hold_confirmed": ai_diag.get("breakout_hold_confirmed"),
            "wick_trap": ai_diag.get("wick_trap"),
            "timing_risk_profile": risk_profile,
            "qty_reduced_for_timing": adjusted_qty < base_qty,
            "qty_reduced_for_loss_brake": loss_brake_multiplier < 0.999,
            "loss_brake_profile": loss_brake,
            "start_trade_allowed": ai_diag.get("start_trade_allowed"),
            "start_trade_decision": ai_diag.get("start_trade_decision"),
            "premium_movement_ok": premium_movement_ok,
            "premium_movement_detail": premium_movement_detail,
        })
    # Prefer the best AI-valid signal that is not blocked by SL cooldown.
    ai_candidates = [r for r in recommendations if (not r.get("blocked_by_cooldown")) and r.get("ai_valid")]
    ai_candidates.sort(
        key=lambda r: (
            float(r.get("ai_edge_score") or 0),
            float(r.get("quality_score") or 0),
            float(r.get("confirmation_score") or r.get("confidence") or 0),
        ),
        reverse=True,
    )
    recommendation = ai_candidates[0] if ai_candidates else None
    # Log/store all recommendations to a file (append as JSON lines)
    try:
        log_path = Path("backend/logs/recommendations.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": _now(),
                "scoring_version": 2,
                "recommendations": recommendations,
                "recommendation_scores": [
                    {
                        "symbol": r.get("symbol"),
                        "ai_edge_score": r.get("ai_edge_score"),
                        "fake_move_risk": r.get("fake_move_risk"),
                        "sudden_news_risk": r.get("sudden_news_risk"),
                        "liquidity_spike_risk": r.get("liquidity_spike_risk"),
                        "premium_distortion_risk": r.get("premium_distortion_risk"),
                        "momentum_score": r.get("momentum_score"),
                        "breakout_score": r.get("breakout_score"),
                        "market_regime": r.get("market_regime"),
                        "thresholds": r.get("thresholds"),
                        "close_back_in_range": r.get("close_back_in_range"),
                        "fake_breakout_by_candle": r.get("fake_breakout_by_candle"),
                        "breakout_hold_confirmed": r.get("breakout_hold_confirmed"),
                        "wick_trap": r.get("wick_trap"),
                        "timing_risk_profile": r.get("timing_risk_profile"),
                        "qty_reduced_for_timing": r.get("qty_reduced_for_timing"),
                        "qty_reduced_for_loss_brake": r.get("qty_reduced_for_loss_brake"),
                        "loss_brake_profile": r.get("loss_brake_profile"),
                        "base_quantity": r.get("base_quantity"),
                        "quantity": r.get("quantity"),
                        "start_trade_allowed": r.get("start_trade_allowed"),
                        "start_trade_decision": r.get("start_trade_decision"),
                    }
                    for r in recommendations
                ],
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
    capital_profile = _capital_protection_profile(balance)
    if not protection_active:
        capital_profile["enabled"] = False
        capital_profile["profile"] = "PAPER_MODE_BYPASS"
        capital_profile["max_position_cap"] = round(float(balance or 0.0), 2)
        capital_profile["max_portfolio_cap"] = round(float(balance or 0.0), 2)
    if protection_active:
        effective_portfolio_cap = min(
            balance * risk_config.get("max_portfolio_pct", 1.0),
            float(capital_profile.get("max_portfolio_cap") or (balance * risk_config.get("max_portfolio_pct", 1.0))),
        )
    else:
        effective_portfolio_cap = float(balance or 0.0)
    remaining_cap = effective_portfolio_cap - capital_in_use
    # Determine if there is enough money for the recommended trade
    required_capital = recommendation["capital_required"] if recommendation else 0
    recommendation_potential_loss = 0.0
    if recommendation:
        recommendation_potential_loss = abs(
            (float(recommendation.get("entry_price") or 0.0) - float(recommendation.get("stop_loss") or 0.0))
            * float(recommendation.get("quantity") or 0.0)
        )
    capital_guard_reasons = _capital_guard_reasons(
        capital_profile,
        capital_required=float(required_capital or 0.0),
        potential_loss=float(recommendation_potential_loss),
        capital_in_use=float(capital_in_use or 0.0),
    ) if recommendation else []
    can_trade = (
        len(active_trades) < MAX_TRADES and remaining_cap >= required_capital and required_capital > 0
    )
    min_live_balance = float(risk_config.get("capital_min_balance") or 0.0)
    if live_balance_only_mode:
        if float(balance or 0.0) < min_live_balance:
            can_trade = False
            capital_guard_reasons = [
                *capital_guard_reasons,
                f"balance_below_min({float(balance or 0.0):.2f}<{min_live_balance:.2f})",
            ]
        else:
            can_trade = len(active_trades) < MAX_TRADES and _has_live_balance_for_trade(balance, required_capital)
    if capital_guard_reasons:
        can_trade = False
    if protection_active and loss_brake.get("block_new_entries"):
        can_trade = False
    simultaneous_reasons: List[str] = []
    if any(t.get("status") == "OPEN" for t in active_trades):
        simultaneous_ok, simultaneous_reasons = _can_allow_additional_live_trade(recommendation)
        if SINGLE_ACTIVE_TRADE and not simultaneous_ok:
            can_trade = False


    # Optionally auto-trigger trade execution for each recommendation
    auto_trade_result = None
    # Allow auto-execution when enabled AND either protection is active (live) or we're in demo mode
    demo_mode = bool(state.get("is_demo_mode", False))
    if allow_auto_execute and (protection_active or demo_mode) and can_trade and recommendation and recommendation.get("start_trade_allowed"):
        try:
            from fastapi import Request
            # Demo mode should be explicit; keep live execution live when armed.
            force_demo = bool(state.get("is_demo_mode", False))
            auto_trade_result = await execute(
                symbol=recommendation["symbol"],
                side=recommendation["action"],
                quantity=recommendation["quantity"],
                price=recommendation["entry_price"],
                balance=balance,
                quality_score=recommendation.get("quality_score"),
                confirmation_score=recommendation.get("confirmation_score") or recommendation.get("confidence"),
                option_type=recommendation.get("option_type"),
                trend_direction=recommendation.get("trend_direction"),
                ai_edge_score=recommendation.get("ai_edge_score"),
                force_demo=force_demo,
                authorization=authorization,
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
        # Not executing: show the trade as simulated, do not execute
        if recommendation:
            auto_trade_result = {
                "executed": False,
                "capital_required": recommendation["capital_required"],
                "potential_profit": round((recommendation["target"] - recommendation["entry_price"]) * recommendation["quantity"], 2),
                "potential_loss": round((recommendation["entry_price"] - recommendation["stop_loss"]) * recommendation["quantity"], 2),
                "message": "Trade not auto-started (capital, availability, or start-trade gate) or auto-execution disabled.",
                "demo_mode": True,
                "loss_brake": loss_brake,
                "capital_protection": capital_profile,
                "capital_guard_reasons": capital_guard_reasons,
                "simultaneous_reasons": simultaneous_reasons,
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
        "live_armed": state.get("live_armed", True),
        "protection_active": protection_active,
        "live_start_rule": "BALANCE_ONLY" if live_balance_only_mode else "PROTECTED",
        "data_source": data_source,
        "can_trade": can_trade,
        "available_sides": available_sides,
        "remaining_capital": round(max(0.0, remaining_cap), 2),
        "capital_in_use": round(capital_in_use, 2),
        "portfolio_cap": round(effective_portfolio_cap, 2),
        "capital_protection": capital_profile,
        "capital_guard_reasons": capital_guard_reasons,
        "simultaneous_reasons": simultaneous_reasons,
        "loss_brake_profile": loss_brake,
        "timestamp": _now(),
        "auto_trade_result": auto_trade_result,
        "blocked_recommendations": blocked_recommendations,
        "ai_rejected_recommendations": ai_rejected_recommendations,
    }

    return response


@router.post("/diagnose")
async def diagnose(
    symbols: Optional[str] = Body(None, embed=True),
    instrument_type: str = Body("weekly_option", embed=True),
    balance: float = Body(50000.0, embed=True),
    authorization: Optional[str] = Header(None),
):
    """Run analysis without performing auto-execution and return gating diagnostics."""
    # Reuse analyze logic but disable auto-execution
    resp = await analyze(symbol="NIFTY", balance=balance, symbols=symbols, instrument_type=instrument_type, quantity=None, authorization=authorization, allow_auto_execute=False)

    # Build diagnostic summary
    diag = {
        "protection_active": resp.get("protection_active"),
        "live_armed": resp.get("live_armed"),
        "is_demo_mode": resp.get("is_demo_mode"),
        "can_trade": resp.get("can_trade"),
        "capital_guard_reasons": resp.get("capital_guard_reasons"),
        "loss_brake_profile": resp.get("loss_brake_profile"),
        "blocked_recommendations": resp.get("blocked_recommendations"),
        "ai_rejected_recommendations": resp.get("ai_rejected_recommendations"),
        "recommendation": resp.get("recommendation"),
        "auto_trade_result": resp.get("auto_trade_result"),
        "timestamp": resp.get("timestamp"),
    }
    return {"diagnostic": diag, **resp}


try:
    BaseModel
except NameError:
    from pydantic import BaseModel as _BaseModel
    BaseModel = _BaseModel


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
    request: Request,
    trade: Optional[TradeRequest] = Body(None),
    symbol: Optional[str] = Query(None),
    price: float = Query(0.0),
    balance: float = Query(100.0),
    quantity: Optional[int] = Query(None),
    side: str = Query("BUY"),
    stop_loss: Optional[float] = Query(None),
    target: Optional[float] = Query(None),
    support: Optional[float] = Query(None),
    resistance: Optional[float] = Query(None),
    broker_id: int = Query(1),
    quality_score: Optional[float] = Query(None),
    confirmation_score: Optional[float] = Query(None),
    ai_edge_score: Optional[float] = Query(None),
    option_type: Optional[str] = Query(None),
    trend_direction: Optional[str] = Query(None),
    trend_strength: Optional[str] = Query(None),
    force_demo: bool = Body(False),
    authorization: Optional[str] = Header(None),
):
    # Accept both body formats:
    # 1) {"trade": {...}, "force_demo": false}
    # 2) Flat payload used by frontend: {"symbol": ..., "price": ..., ...}
    if trade is None:
        try:
            payload = await request.json()
            if isinstance(payload, dict) and payload:
                force_demo = bool(payload.get("force_demo", force_demo))
                symbol = payload.get("symbol", symbol)
                if payload.get("price") is not None:
                    price = float(payload.get("price"))
                if payload.get("balance") is not None:
                    balance = float(payload.get("balance"))
                if payload.get("quantity") is not None:
                    quantity = int(payload.get("quantity"))
                side = payload.get("side", side)
                stop_loss = payload.get("stop_loss", stop_loss)
                target = payload.get("target", target)
                support = payload.get("support", support)
                resistance = payload.get("resistance", resistance)
                broker_id = int(payload.get("broker_id", broker_id))
                quality_score = payload.get("quality_score", quality_score)
                confirmation_score = payload.get("confirmation_score", confirmation_score)
                ai_edge_score = payload.get("ai_edge_score", ai_edge_score)
                option_type = payload.get("option_type", option_type)
                trend_direction = payload.get("trend_direction", trend_direction)
                trend_strength = payload.get("trend_strength", trend_strength)
        except Exception:
            # Ignore malformed/non-JSON body and continue with query/body defaults.
            pass

    # Resolve parameters from JSON body `trade` if provided (body takes precedence)
    if trade is not None:
        symbol = trade.symbol
        price = float(trade.price or price or 0.0)
        balance = float(trade.balance or balance or 0.0)
        quantity = trade.quantity
        side = trade.side or side
        stop_loss = trade.stop_loss
        target = trade.target
        support = trade.support
        resistance = trade.resistance
        broker_id = int(trade.broker_id or broker_id)
        expiry = getattr(trade, 'expiry', None)

    # Hard gate: never allow new trade execution outside configured market window.
    if not _within_trade_window():
        market = market_status(dt_time(9, 15), dt_time(15, 30))
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Market is closed. New trade execution is blocked outside market hours.",
                "market_open": market.get("is_open", False),
                "market_reason": market.get("reason", "Market closed"),
                "current_time": market.get("current_time"),
            },
        )

    mode = "LIVE"

    # Demo mode: when explicitly set OR when balance=0 (frontend's way of indicating paper/demo trading)
    auto_demo = bool(state.get("is_demo_mode")) or bool(force_demo) or (balance <= 0)
    live_balance_only_mode = _live_protection_active() and bool(risk_config.get("live_start_balance_only", False)) and (not auto_demo)
    loss_brake = _loss_brake_profile()
    if loss_brake.get("block_new_entries") and not auto_demo:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "New trades blocked by dynamic loss brake.",
                "loss_brake": loss_brake,
            },
        )

    try:
        trade = TradeRequest(
            symbol=symbol,
            price=price,
            balance=balance,
            quantity=quantity,
            side=side,
            stop_loss=stop_loss,
            target=target,
            support=support,
            resistance=resistance,
            broker_id=broker_id,
        )
    except Exception as validation_error:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid trade payload.",
                "error": str(validation_error),
            },
        )

    # Optional server-side AI enforcement when metadata is provided.
    ai_context = {
        "symbol": symbol,
        "entry_price": price,
        "target": target,
        "stop_loss": stop_loss,
        "quality_score": quality_score,
        "confirmation_score": confirmation_score,
        "ai_edge_score": ai_edge_score,
        "option_type": option_type,
        "trend_direction": trend_direction,
        "trend_strength": trend_strength,
    }
    if (not auto_demo) and any(v is not None for v in [quality_score, confirmation_score, option_type, trend_direction]):
        ai_ok, ai_reasons, _ = _ai_entry_validation(ai_context, loss_brake=loss_brake)
        if not ai_ok:
            print(f"[AI GATE] Rejected trade {symbol} reasons={ai_reasons}")
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Trade rejected by server-side AI quality gate.",
                    "reasons": ai_reasons,
                    "ai_context": ai_context,
                },
            )

    max_consecutive_losses = int(risk_config.get("max_consecutive_losses") or 0)
    if max_consecutive_losses > 0 and int(state.get("consecutive_losses") or 0) >= max_consecutive_losses and not auto_demo:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Trading blocked due to consecutive loss limit.",
                "consecutive_losses": int(state.get("consecutive_losses") or 0),
                "max_consecutive_losses": max_consecutive_losses,
            },
        )

    option_kind = _option_kind(trade.symbol)

    # ═══════════════════════════════════════════════════════════════
    # 10-POINT MAX STOP LOSS VALIDATION (NEW)
    # ═══════════════════════════════════════════════════════════════
    
    pct = STOP_PCT / 100
    derived_stop = trade.stop_loss
    if option_kind:
        stop_move = trade.price * (STOP_PCT_OPTIONS / 100)
        if trade.side.upper() == "SELL":
            computed_stop = round(trade.price + stop_move, 2)
            # Keep strict SL: never widen risk if client provided a tighter protective stop.
            if trade.stop_loss is not None and trade.stop_loss > trade.price:
                derived_stop = round(min(computed_stop, float(trade.stop_loss)), 2)
            else:
                derived_stop = computed_stop
        else:
            computed_stop = round(trade.price - stop_move, 2)
            # Keep strict SL: never widen risk if client provided a tighter protective stop.
            if trade.stop_loss is not None and trade.stop_loss < trade.price:
                derived_stop = round(max(computed_stop, float(trade.stop_loss)), 2)
            else:
                derived_stop = computed_stop
    elif derived_stop is None:
        if trade.side.upper() == "BUY":
            derived_stop = round(trade.price * (1 - pct), 2)
        else:
            derived_stop = round(trade.price * (1 + pct), 2)

    # --- ATR-based dynamic stop override (more robust for volatile moves) ---
    try:
        if atr_config.get("enabled", False):
            underlying = _extract_underlying_symbol(trade.symbol)
            candles = _fetch_recent_candles(underlying, candle_count=30)
            if candles and len(candles) >= atr_config.get("min_candles", 5):
                # compute true range list without pandas
                trs = []
                prev_close = None
                for c in candles:
                    h = float(c.get("high", 0))
                    l = float(c.get("low", 0))
                    cl = float(c.get("close", 0))
                    if prev_close is None:
                        tr = h - l
                    else:
                        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
                    trs.append(tr)
                    prev_close = cl

                # Use rolling mean of last N values (period)
                period = int(atr_config.get("period", 14))
                sample = trs[-period:] if len(trs) >= period else trs
                if sample:
                    atr = sum(sample) / len(sample)
                    if option_kind:
                        # scale underlying ATR to an approximate option-premium movement
                        scale = float(atr_config.get("option_scale", 0.45))
                        atr_points = max(1.0, round(atr * scale, 2))
                        if trade.side.upper() == "BUY":
                            suggested = round(trade.price - atr_points, 2)
                            # if client provided a tighter SL, keep it, else use ATR-based
                            if trade.stop_loss is None:
                                derived_stop = suggested
                            else:
                                # never widen provided protective stop
                                if trade.stop_loss < trade.price:
                                    derived_stop = round(max(suggested, float(trade.stop_loss)), 2)
                        else:
                            suggested = round(trade.price + atr_points, 2)
                            if trade.stop_loss is None:
                                derived_stop = suggested
                            else:
                                if trade.stop_loss > trade.price:
                                    derived_stop = round(min(suggested, float(trade.stop_loss)), 2)
                    else:
                        atr_points = round(atr * float(atr_config.get("multiplier", 1.0)), 2)
                        if trade.side.upper() == "BUY":
                            suggested = round(trade.price - atr_points, 2)
                            if trade.stop_loss is None:
                                derived_stop = suggested
                            else:
                                if trade.stop_loss < trade.price:
                                    derived_stop = round(max(suggested, float(trade.stop_loss)), 2)
                        else:
                            suggested = round(trade.price + atr_points, 2)
                            if trade.stop_loss is None:
                                derived_stop = suggested
                            else:
                                if trade.stop_loss > trade.price:
                                    derived_stop = round(min(suggested, float(trade.stop_loss)), 2)
    except Exception:
        # ATR best-effort: ignore errors and continue with previously derived_stop
        pass
    
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

    capital_required = round(float(trade.price or 0.0) * float(qty or 0), 2)
    live_balance_value = float(trade.balance or balance or 0.0)
    min_live_balance = float(risk_config.get("capital_min_balance") or 0.0)
    if live_balance_only_mode and live_balance_value < min_live_balance:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Live balance below minimum required for trading.",
                "min_balance": round(min_live_balance, 2),
                "balance": round(live_balance_value, 2),
            },
        )

    if live_balance_only_mode and not _has_live_balance_for_trade(live_balance_value, capital_required):
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Insufficient available balance for live trade.",
                "required": capital_required,
                "balance": round(live_balance_value, 2),
                "capital_in_use": round(float(_capital_in_use() or 0.0), 2),
            },
        )

    capital_profile = _capital_protection_profile(float(trade.balance or balance or 0.0))
    guard_reasons = _capital_guard_reasons(
        capital_profile,
        capital_required=capital_required,
        potential_loss=float(potential_loss or 0.0),
        capital_in_use=float(_capital_in_use() or 0.0),
    )
    if guard_reasons and not auto_demo:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Trade blocked by strict capital protection profile.",
                "reasons": guard_reasons,
                "capital_protection": capital_profile,
            },
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

        existing_open = [t for t in active_trades if t.get("status") == "OPEN"]
        if existing_open and (not auto_demo):
            simultaneous_ok, simultaneous_reasons = _can_allow_additional_live_trade(ai_context)
            if SINGLE_ACTIVE_TRADE and not simultaneous_ok:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": "Concurrent live trade blocked by quality/diversification gate.",
                        "reasons": simultaneous_reasons,
                    },
                )

        blocked, wait_seconds, cooldown_key = _cooldown_info(trade.symbol, trade.side)
        if blocked and not auto_demo:
            wait_seconds_rounded = int(math.ceil(wait_seconds))
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "SL cooldown active for this trade side/symbol.",
                    "cooldown_key": cooldown_key,
                    "wait_seconds": wait_seconds_rounded,
                },
            )

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
        # Server-side multi-tick confirmation guard to reduce false entries
        underlying = _extract_underlying_symbol(trade.symbol)
        try:
            confirmed = _require_multi_tick_confirmation(underlying, trade.price, trade.side, required_ticks=3)
        except Exception as confirmation_error:
            print(f"[API /execute] Multi-tick confirmation failed for {trade.symbol}: {confirmation_error}")
            confirmed = False

        if not confirmed and not auto_demo:
            raise HTTPException(status_code=403, detail={
                "message": "Trade blocked: failed multi-tick confirmation (server guard).",
                "underlying": underlying,
                "required_ticks": 3,
            })

        # If demo mode is active or live is not armed, create a simulated/demo trade instead of placing a real order.
        if auto_demo or (not bool(state.get("live_armed", True))):
            trade_obj["status"] = "DEMO"
            trade_obj["entry_time"] = _now()
            trade_obj["broker_response"] = {"simulated": True}
            demo_trades.append(trade_obj)
            active_trades.append(trade_obj)
            broker_response = {"simulated": True}
            print(f"[API /execute] ℹ Demo trade started for {trade_obj.get('symbol')} qty={trade_obj.get('quantity')}")
        else:
            print(f"[API /execute] ▶ Placing {mode} order to Zerodha...")
            print(f"[API /execute] ▶ Order Details: {zerodha_symbol}, {trade.quantity or 1} qty, {trade.side} at ₹{trade.price}")
            try:
                real_order = place_zerodha_order(
                    symbol=zerodha_symbol,
                    quantity=trade.quantity or 1,
                    side=trade.side,
                    order_type="MARKET",
                    product="MIS",
                    exchange="NFO"  # Use 'NFO' for options
                )
            except Exception as order_error:
                print(f"[API /execute] ✗ Zerodha order exception: {order_error}")
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": "Live broker order placement failed.",
                        "error": str(order_error),
                    },
                )
            if real_order.get("success"):
                print(f"[API /execute] ✓ Zerodha order ACCEPTED - Order ID: {real_order.get('order_id', 'N/A')}")
                broker_response = real_order
                active_trades.append(trade_obj)
            else:
                print(f"[API /execute] ✗ Zerodha order REJECTED - Error: {real_order.get('error', 'Unknown')}")
                return {
                    "success": False,
                    "message": real_order.get("error"),
                    "timestamp": _now(),
                }

        broker_logs.append({"trade": trade_obj, "response": broker_response})

        return {
            "success": True,
            "is_demo_mode": auto_demo,
            "message": f"{mode} trade accepted for {trade.symbol} at {trade.price}",
            "live_start_rule": "BALANCE_ONLY" if live_balance_only_mode else "PROTECTED",
            "timestamp": _now(),
            "broker_response": broker_response,
            "stop_loss": derived_stop,
            "target": derived_target,
            "capital_protection": capital_profile,
        }


@router.get("/trades/active")
async def get_active_trades(authorization: Optional[str] = Header(None)):
    print(f"[API /trades/active] Returning {len(active_trades)} active trades from Zerodha")
    trades = [normalize_active_trade_metrics(trade) for trade in active_trades]
    active_trades[:] = trades
    return {"trades": trades, "is_demo_mode": False, "count": len(trades)}


@router.post("/trades/update-prices")
async def update_live_trade_prices(authorization: Optional[str] = Header(None)):
    try:
        return {
            "success": True,
            "is_demo_mode": state.get("is_demo_mode", False),
            "updated_count": 0,
            "closed_count": 0,
            "message": "Updated",
            "timestamp": _now(),
        }
    except Exception as e:
        return {"success": False, "message": str(e), "updated_count": 0}


@router.post("/trades/close")
async def close_live_trade(payload: CloseTradeRequest, authorization: Optional[str] = Header(None)):
    target_trade = None

    if payload.trade_id is not None:
        for trade in active_trades:
            if trade.get("status") == "OPEN" and trade.get("id") == payload.trade_id:
                target_trade = trade
                break

    if target_trade is None and payload.symbol:
        for trade in reversed(active_trades):
            if trade.get("status") == "OPEN" and trade.get("symbol") == payload.symbol:
                target_trade = trade
                break

    if target_trade is None:
        raise HTTPException(status_code=404, detail="Open trade not found")

    exit_price = float(
        target_trade.get("current_price")
        or target_trade.get("entry_price")
        or target_trade.get("price")
        or 0.0
    )
    target_trade["status"] = "MANUAL_CLOSE"
    target_trade["exit_reason"] = "MANUAL_CLOSE"
    _close_trade(target_trade, exit_price)

    active_trades[:] = [t for t in active_trades if t.get("status") == "OPEN"]

    return {
        "success": True,
        "message": "Trade closed manually",
        "closed_trade": normalize_active_trade_metrics(target_trade),
        "active_count": len(active_trades),
        "history_count": len(history),
    }


@router.post("/trades/price")
async def update_trade_price(symbol: str, price: float, authorization: Optional[str] = Header(None)):
    updated = 0
    closed = 0
    to_close = []
    for trade in active_trades:
        if trade.get("symbol") == symbol and trade.get("status") == "OPEN":
            prev_price = float(trade.get("current_price") or trade.get("price") or price)
            _maybe_update_trail(trade, price)
            trade["current_price"] = price
            updated += 1

            try:
                side = (trade.get("side") or "BUY").upper()
                entry = float(trade.get("price") or trade.get("entry_price") or 0.0)
                profit_points = round((price - entry) * (1 if side == "BUY" else -1), 2)
            except Exception:
                profit_points = 0

            LOCK_POINTS = 20
            if profit_points >= LOCK_POINTS and not trade.get("profit_lock_applied"):
                if side == "BUY":
                    locked_sl = round(entry + LOCK_POINTS, 2)
                    trade["stop_loss"] = max(trade.get("stop_loss", entry - LOCK_POINTS), locked_sl)
                else:
                    locked_sl = round(entry - LOCK_POINTS, 2)
                    trade["stop_loss"] = min(trade.get("stop_loss", entry + LOCK_POINTS), locked_sl)
                trade["profit_lock_applied"] = True

            if trade.get("profit_lock_applied"):
                if side == "BUY" and price < prev_price:
                    trade["status"] = "SL_HIT"
                    trade["exit_reason"] = "SL_HIT"
                    _maybe_place_exit_order(trade, price)
                    _close_trade(trade, price)
                    to_close.append(trade)
                    closed += 1
                    continue
                if side != "BUY" and price > prev_price:
                    trade["status"] = "SL_HIT"
                    trade["exit_reason"] = "SL_HIT"
                    _maybe_place_exit_order(trade, price)
                    _close_trade(trade, price)
                    to_close.append(trade)
                    closed += 1
                    continue

            exit_reason = _should_exit_by_currency(trade, price)
            if exit_reason:
                trade["status"] = exit_reason
                trade["exit_reason"] = exit_reason
                _maybe_place_exit_order(trade, price)
                _close_trade(trade, price)
                to_close.append(trade)
                closed += 1
                continue
            if _stop_hit(trade, price):
                trade["status"] = "SL_HIT"
                trade["exit_reason"] = "SL_HIT"
                _maybe_place_exit_order(trade, price)
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


@router.post("/auto_scan/start")
async def start_auto_scan(
    interval: Optional[float] = Body(3, embed=True),
    symbols: Optional[str] = Body("NIFTY,BANKNIFTY", embed=True),
    instrument_type: Optional[str] = Body("weekly_option", embed=True),
    balance: Optional[float] = Body(None, embed=True),
    authorization: Optional[str] = Header(None),
):
    """Start background auto-scan worker. Polls every `interval` seconds."""
    global auto_scan_task, auto_scan_state
    if auto_scan_state.get("running"):
        return {"running": True, "message": "Auto-scan already running", "state": auto_scan_state}

    auto_scan_state.update({
        "running": True,
        "interval": max(1.0, float(interval or 3)),
        "symbols": [s.strip().upper() for s in (symbols or "").split(",") if s.strip()],
        "instrument_type": instrument_type or "weekly_option",
    })

    # If caller did not supply a balance, try to fetch from active Zerodha credentials
    resolved_balance: Optional[float] = None
    if balance is not None:
        try:
            resolved_balance = float(balance)
        except Exception:
            resolved_balance = None

    if resolved_balance is None:
        # attempt to read active Zerodha broker credentials and fetch balance
        try:
            db = SessionLocal()
            cred = (
                db.query(BrokerCredential)
                .filter(BrokerCredential.broker_name.ilike("%zerodha%"), BrokerCredential.is_active == True)
                .order_by(BrokerCredential.id.desc())
                .first()
            )
            if cred:
                zb = ZerodhaBroker()
                creds = {"api_key": getattr(cred, "api_key", None), "access_token": getattr(cred, "access_token", None)}
                if zb.connect(creds):
                    bal_resp = zb.get_balance()
                    if isinstance(bal_resp, dict) and bal_resp.get("success"):
                        funds = bal_resp.get("funds") or {}
                        # try common keys returned by brokers
                        for key in ("available", "available_cash", "equity", "net", "cash", "cash_available"):
                            if key in funds:
                                try:
                                    resolved_balance = float(funds[key])
                                    break
                                except Exception:
                                    continue
                        # if still not found, try numeric aggregation
                        if resolved_balance is None and isinstance(funds, dict):
                            nums = [v for v in funds.values() if isinstance(v, (int, float))]
                            if nums:
                                resolved_balance = float(sum(nums))
        except Exception:
            resolved_balance = None
        finally:
            try:
                db.close()
            except Exception:
                pass

    # fallback: use last known state or zero (no hard-coded magic number)
    auto_scan_state["balance"] = float(resolved_balance or auto_scan_state.get("balance") or 0.0)
    auto_scan_task = asyncio.create_task(_auto_scan_worker())
    return {"running": True, "state": auto_scan_state}


@router.post("/auto_scan/stop")
async def stop_auto_scan(authorization: Optional[str] = Header(None)):
    global auto_scan_task, auto_scan_state
    auto_scan_state["running"] = False
    if auto_scan_task:
        try:
            auto_scan_task.cancel()
        except Exception:
            pass
        auto_scan_task = None
    return {"running": False, "state": auto_scan_state}


@router.get("/auto_scan/status")
async def auto_scan_status(authorization: Optional[str] = Header(None)):
    return {"state": auto_scan_state}

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
