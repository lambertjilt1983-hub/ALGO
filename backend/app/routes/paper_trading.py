"""
Paper Trading API
Track signal performance without real execution
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, date, timedelta, time as dt_time
from typing import List, Optional
from pydantic import BaseModel
import math
import re

from app.core.database import get_db
from app.core.market_hours import market_status
from app.models.trading import PaperTrade

router = APIRouter()

# Paper Trading Quality Gates (NEW)
PAPER_QUALITY_SCORE_MINIMUM = 66
PAPER_CONFIRMATION_SCORE_MINIMUM = 70
PAPER_AI_EDGE_MINIMUM = 35.0
PAPER_ENTRY_RR_MINIMUM = 1.30
PAPER_REQUIRE_BOTH_CONFIRMATIONS = True
PAPER_MARKET_REGIME_FILTER = True
PAPER_ENFORCE_DAILY_LIMITS = True
PAPER_MAX_DAILY_TRADES = 14
PAPER_CONSECUTIVE_SL_HIT_LIMIT = 2
PAPER_DAILY_PROFIT_TARGET = 5000.0
PAPER_MAX_FAKE_MOVE_RISK = 16.0
PAPER_MAX_NEWS_RISK = 18.0
PAPER_MAX_LIQUIDITY_SPIKE_RISK = 16.0
PAPER_MAX_PREMIUM_DISTORTION = 14.0

# Paper Trading SL/Re-entry Settings
MAX_PAPER_TRADES = 1  # Only one paper trade at a time
PAPER_SL_COOLDOWN_MINUTES = 5
PAPER_REENTRY_GUARD_MINUTES = 20
PAPER_REENTRY_MIN_QUALITY_IMPROVEMENT = 6.0
PAPER_REENTRY_MIN_AI_EDGE_IMPROVEMENT = 8.0
PAPER_REENTRY_MIN_BREAKOUT_IMPROVEMENT = 10.0
PAPER_PROFIT_LOCK_POINTS = 20.0


def _option_kind(symbol: str | None) -> str | None:
    if not symbol:
        return None
    upper = symbol.upper()
    if upper.endswith("CE"):
        return "CE"
    if upper.endswith("PE"):
        return "PE"
    return None


def _symbol_root(symbol: str | None) -> str:
    """Normalize option/equity symbol to a root (e.g., BANKNIFTY26MAR... -> BANKNIFTY)."""
    if not symbol:
        return ""
    s = symbol.upper().strip()
    s = re.sub(r'^(NFO:|NSE:|BFO:|BSE:)', '', s)
    match = re.match(r'([A-Z]+)', s)
    return match.group(1) if match else s


def _paper_sl_cooldown_info(db: Session, symbol: str, side: str, minutes: int = PAPER_SL_COOLDOWN_MINUTES):
    """Return cooldown status after SL_HIT for same symbol/root + side."""
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=minutes)
    normalized_side = (side or "BUY").upper()
    requested_symbol = (symbol or "").upper()
    requested_root = _symbol_root(requested_symbol)

    recent_sl = db.query(PaperTrade).filter(
        and_(
            PaperTrade.status == "SL_HIT",
            PaperTrade.side == normalized_side,
            PaperTrade.exit_time.isnot(None),
            PaperTrade.exit_time >= cutoff,
        )
    ).order_by(PaperTrade.exit_time.desc()).all()

    for trade in recent_sl:
        closed_symbol = (trade.symbol or "").upper()
        closed_root = _symbol_root(closed_symbol)
        same_symbol = closed_symbol == requested_symbol
        same_root = bool(requested_root) and requested_root == closed_root
        if not (same_symbol or same_root):
            continue

        elapsed = (now - trade.exit_time).total_seconds()
        remaining = max(0, int(minutes * 60 - elapsed))
        if remaining > 0:
            return True, remaining, {
                "blocked_by": "SL_HIT_COOLDOWN",
                "last_sl_trade_id": trade.id,
                "last_sl_symbol": trade.symbol,
                "cooldown_minutes": minutes,
            }

    return False, 0, None


def _paper_boolish(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _paper_num(value, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default


def _paper_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _paper_compute_rr(entry_price, target, stop_loss) -> float:
    try:
        entry = _paper_num(entry_price)
        tgt = _paper_num(target)
        sl = _paper_num(stop_loss)
        risk = abs(entry - sl)
        reward = abs(tgt - entry)
        return (reward / risk) if risk > 0 else 0.0
    except Exception:
        return 0.0


def _paper_same_move_exit_status(trade_or_dict) -> str:
    status = str(getattr(trade_or_dict, "status", None) or trade_or_dict.get("status") or "").upper()
    if status != "SL_HIT":
        return status
    side = str(getattr(trade_or_dict, "side", None) or trade_or_dict.get("side") or "BUY").upper()
    entry = _paper_num(getattr(trade_or_dict, "entry_price", None) if hasattr(trade_or_dict, "entry_price") else trade_or_dict.get("entry_price"))
    exit_price = _paper_num(getattr(trade_or_dict, "exit_price", None) if hasattr(trade_or_dict, "exit_price") else trade_or_dict.get("exit_price"))
    stop_loss_raw = getattr(trade_or_dict, "stop_loss", None) if hasattr(trade_or_dict, "stop_loss") else trade_or_dict.get("stop_loss")
    stop_loss = _paper_num(stop_loss_raw) if stop_loss_raw is not None else None
    pnl = _paper_num(getattr(trade_or_dict, "pnl", None) if hasattr(trade_or_dict, "pnl") else trade_or_dict.get("pnl"))
    favorable_stop = stop_loss is not None and ((side == "BUY" and stop_loss > entry) or (side == "SELL" and stop_loss < entry))
    favorable_exit = (side == "BUY" and exit_price > entry) or (side == "SELL" and exit_price < entry)
    lock_move = abs(exit_price - entry) >= PAPER_PROFIT_LOCK_POINTS
    if pnl > 0 and favorable_exit and (favorable_stop or lock_move):
        return "PROFIT_TRAIL"
    return status


def _backfill_paper_profit_trail_rows(db: Session) -> int:
    candidates = db.query(PaperTrade).filter(PaperTrade.status == "SL_HIT").all()
    updated = 0
    for trade in candidates:
        next_status = _paper_same_move_exit_status(trade)
        if next_status != trade.status:
            trade.status = next_status
            updated += 1
    if updated:
        db.commit()
    return updated


def _paper_count_daily_trades(db: Session) -> int:
    """Count how many paper trades have been created today."""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, dt_time(0, 0, 0))
    today_end = datetime.combine(today, dt_time(23, 59, 59))
    
    count = db.query(func.count(PaperTrade.id)).filter(
        and_(
            PaperTrade.entry_time >= today_start,
            PaperTrade.entry_time <= today_end,
        )
    ).scalar() or 0
    
    return count


def _paper_count_consecutive_sl_hits(db: Session) -> int:
    """Count consecutive SL_HIT trades from the end of today's history."""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, dt_time(0, 0, 0))
    
    today_trades = db.query(PaperTrade).filter(
        PaperTrade.exit_time >= today_start
    ).order_by(PaperTrade.exit_time.desc()).all()
    
    consecutive = 0
    for trade in today_trades:
        if trade.status == "SL_HIT":
            consecutive += 1
        else:
            break
    
    return consecutive


def _paper_get_daily_pnl(db: Session) -> float:
    """Calculate today's P&L (sum of all closed paper trades + open P&L)."""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, dt_time(0, 0, 0))
    
    pnl = 0.0
    
    # Sum P&L from all closed trades today
    closed_pnl = db.query(func.sum(PaperTrade.pnl)).filter(
        and_(
            PaperTrade.status != "OPEN",
            PaperTrade.exit_time >= today_start,
        )
    ).scalar()
    
    pnl += closed_pnl or 0.0
    
    # Add unrealized P&L from open trade
    open_trade = db.query(PaperTrade).filter(
        and_(
            PaperTrade.status == "OPEN",
            PaperTrade.entry_time >= today_start,
        )
    ).first()
    
    if open_trade:
        current_price = open_trade.current_price or open_trade.entry_price
        if current_price > 0 and open_trade.entry_price > 0:
            side = (open_trade.side or "BUY").upper()
            qty = open_trade.quantity or 1
            unrealized = (current_price - open_trade.entry_price) * qty if side == "BUY" else (open_trade.entry_price - current_price) * qty
            pnl += unrealized
    
    return pnl


def _paper_should_allow_new_trade(db: Session) -> tuple:
    """Check if we should allow a new paper trade based on quality gates and daily limits."""
    daily_trades = _paper_count_daily_trades(db)
    max_daily = PAPER_MAX_DAILY_TRADES
    
    if daily_trades >= max_daily:
        return False, f"max_daily_trades_reached ({daily_trades}/{max_daily})"
    
    consecutive_sl = _paper_count_consecutive_sl_hits(db)
    sl_limit = PAPER_CONSECUTIVE_SL_HIT_LIMIT
    
    if consecutive_sl >= sl_limit:
        return False, f"consecutive_sl_hit_limit_reached ({consecutive_sl}/{sl_limit}) - market is choppy, pause entries"
    
    daily_pnl = _paper_get_daily_pnl(db)
    
    if daily_pnl >= PAPER_DAILY_PROFIT_TARGET:
        return False, f"daily_profit_target_reached (₹{daily_pnl:.0f} >= ₹{PAPER_DAILY_PROFIT_TARGET:.0f}) - good day, stop trading"
    
    return True, None


def _paper_recent_reentry_guard(db: Session, trade: "PaperTradeCreate"):
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=PAPER_REENTRY_GUARD_MINUTES)
    normalized_side = (trade.side or "BUY").upper()
    requested_root = _symbol_root(trade.symbol)
    requested_kind = _option_kind(trade.symbol)
    recent = db.query(PaperTrade).filter(
        and_(
            PaperTrade.status != "OPEN",
            PaperTrade.status != "MANUAL_CLOSE",
            PaperTrade.status != "EXPIRED",
            PaperTrade.side == normalized_side,
            PaperTrade.exit_time.isnot(None),
            PaperTrade.exit_time >= cutoff,
        )
    ).order_by(PaperTrade.exit_time.desc()).all()

    signal_data = _paper_dict(trade.signal_data)
    current_quality = _paper_num(signal_data.get("quality_score") or signal_data.get("quality"))
    current_ai_edge = _paper_num(signal_data.get("ai_edge_score"))
    current_breakout = _paper_num(signal_data.get("breakout_score"))
    current_momentum = _paper_num(signal_data.get("momentum_score"))
    start_trade_allowed = _paper_boolish(signal_data.get("start_trade_allowed"))
    breakout_confirmed = _paper_boolish(signal_data.get("breakout_confirmed"))
    momentum_confirmed = _paper_boolish(signal_data.get("momentum_confirmed"))
    breakout_hold_confirmed = _paper_boolish(signal_data.get("breakout_hold_confirmed"))
    close_back_in_range = _paper_boolish(signal_data.get("close_back_in_range"))
    fake_breakout_by_candle = _paper_boolish(signal_data.get("fake_breakout_by_candle"))

    for previous in recent:
        previous_root = _symbol_root(previous.symbol)
        previous_kind = _option_kind(previous.symbol)
        if previous_root != requested_root:
            continue
        if requested_kind and previous_kind and requested_kind != previous_kind:
            continue

        prev_signal = _paper_dict(previous.signal_data)
        prev_quality = _paper_num(prev_signal.get("quality_score") or prev_signal.get("quality"))
        prev_ai_edge = _paper_num(prev_signal.get("ai_edge_score"))
        prev_breakout = _paper_num(prev_signal.get("breakout_score"))
        prev_momentum = _paper_num(prev_signal.get("momentum_score"))

        fresh_breakout = (
            start_trade_allowed is not False
            and breakout_confirmed is not False
            and momentum_confirmed is not False
            and breakout_hold_confirmed is not False
            and close_back_in_range is not True
            and fake_breakout_by_candle is not True
        )
        stronger_signal = (
            current_quality >= prev_quality + PAPER_REENTRY_MIN_QUALITY_IMPROVEMENT
            or current_ai_edge >= prev_ai_edge + PAPER_REENTRY_MIN_AI_EDGE_IMPROVEMENT
            or current_breakout >= prev_breakout + PAPER_REENTRY_MIN_BREAKOUT_IMPROVEMENT
            or (current_quality >= 92.0 and current_ai_edge >= 70.0 and current_breakout >= max(prev_breakout, 70.0))
            or (current_momentum >= prev_momentum + 8.0 and current_ai_edge >= max(prev_ai_edge, 60.0))
        )
        if fresh_breakout and stronger_signal:
            return False, 0, None

        remaining = max(0, int((previous.exit_time - cutoff).total_seconds()))
        return True, remaining, {
            "blocked_by": "SAME_MOVE_REENTRY_GUARD",
            "last_trade_id": previous.id,
            "last_trade_symbol": previous.symbol,
            "last_trade_status": previous.status,
            "guard_minutes": PAPER_REENTRY_GUARD_MINUTES,
        }

    return False, 0, None


def _yahoo_ticker_for_underlying(underlying: str) -> str:
    mapping = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
        "SENSEX": "^BSESN",
        "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
    }
    return mapping.get(underlying, "^NSEI")


def _fetch_recent_candles(underlying: str, candle_count: int = 3):
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
    except Exception:
        return []


def _require_multi_tick_confirmation(underlying: str, entry_price: float, side: str, required_ticks: int = 3) -> bool:
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
    bypass_confirmation: Optional[bool] = False


class PaperTradeUpdate(BaseModel):
    current_price: Optional[float] = None
    status: Optional[str] = None
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None


@router.post("/paper-trades")
def create_paper_trade(trade: PaperTradeCreate, db: Session = Depends(get_db)):
    """Log a new paper trade signal - only one open trade allowed"""
    _backfill_paper_profit_trail_rows(db)
    market = market_status(dt_time(9, 15), dt_time(15, 29))
    if not market.get("is_open", False):
        return {
            "success": False,
            "message": "Market is closed. New paper trades are blocked outside market hours.",
            "market_open": False,
            "market_reason": market.get("reason", "Market closed"),
            "current_time": market.get("current_time"),
        }

    # NEW: Quality gates to reduce volume to 10-20 trades/day
    signal_data = _paper_dict(trade.signal_data)
    quality_score = _paper_num(signal_data.get("quality_score") or signal_data.get("quality"))
    confirmation_score = _paper_num(signal_data.get("confirmation_score") or signal_data.get("confidence"))
    ai_edge_score = _paper_num(signal_data.get("ai_edge_score"))
    breakout_score = _paper_num(signal_data.get("breakout_score"))
    momentum_score = _paper_num(signal_data.get("momentum_score"))
    market_regime = str(signal_data.get("market_regime") or "").upper()
    market_bias = str(signal_data.get("market_bias") or signal_data.get("trend_direction") or "").upper()
    timing_risk = str(
        signal_data.get("timing_risk")
        or (signal_data.get("timing_risk_profile") or {}).get("window")
        or ""
    ).upper()
    breakout_hold_confirmed = _paper_boolish(signal_data.get("breakout_hold_confirmed"))
    fake_move_risk = _paper_num(signal_data.get("fake_move_risk") or signal_data.get("fake_move_risk_score"))
    news_risk = _paper_num(signal_data.get("news_risk") or signal_data.get("sudden_news_risk") or signal_data.get("news_risk_score"))
    liquidity_spike_risk = _paper_num(signal_data.get("liquidity_spike_risk") or signal_data.get("liquidity_spike_risk_score"))
    premium_distortion = _paper_num(signal_data.get("premium_distortion") or signal_data.get("premium_distortion_risk") or signal_data.get("premium_distortion_score"))
    breakout_confirmed = _paper_boolish(signal_data.get("breakout_confirmed"))
    momentum_confirmed = _paper_boolish(signal_data.get("momentum_confirmed"))
    
    # Relax quality gates slightly for STOCKS vs. INDEX OPTIONS
    signal_is_stock = signal_data.get("signal_type") == "stock" or signal_data.get("is_stock") is True
    rr_value = _paper_compute_rr(trade.entry_price, trade.target, trade.stop_loss)
    rr_value_cmp = round(rr_value, 2)
    
    if signal_is_stock:
        # STOCKS: Slightly more lenient (but still quality-focused)
        quality_gate = PAPER_QUALITY_SCORE_MINIMUM - 5  # 54 vs 59 for indices
        confirmation_gate = PAPER_CONFIRMATION_SCORE_MINIMUM - 5  # 59 vs 64 for indices
        ai_edge_gate = PAPER_AI_EDGE_MINIMUM - 5  # 23 vs 28 for indices
        rr_gate = PAPER_ENTRY_RR_MINIMUM - 0.10  # 1.15 vs 1.25 for indices
        require_both_conf = True
    else:
        # INDEX OPTIONS: Strict thresholds
        quality_gate = PAPER_QUALITY_SCORE_MINIMUM
        confirmation_gate = PAPER_CONFIRMATION_SCORE_MINIMUM
        ai_edge_gate = PAPER_AI_EDGE_MINIMUM
        rr_gate = PAPER_ENTRY_RR_MINIMUM
        require_both_conf = PAPER_REQUIRE_BOTH_CONFIRMATIONS
    
    # Check daily trade and consecutive SL limits
    daily_ok, daily_reason = _paper_should_allow_new_trade(db) if PAPER_ENFORCE_DAILY_LIMITS else (True, "quality_mode_daily_limits_disabled")
    
    quality_gate_rejection = None
    if quality_score < quality_gate:
        quality_gate_rejection = f"quality_score<{quality_gate} (got {quality_score:.1f})"
    elif confirmation_score < confirmation_gate:
        quality_gate_rejection = f"confirmation_score<{confirmation_gate} (got {confirmation_score:.1f})"
    elif ai_edge_score < ai_edge_gate:
        quality_gate_rejection = f"ai_edge_score<{ai_edge_gate} (got {ai_edge_score:.1f})"
    elif rr_value_cmp + 1e-9 < rr_gate:
        quality_gate_rejection = f"rr<{rr_gate:.2f} (got {rr_value_cmp:.2f})"
    if quality_gate_rejection is None and require_both_conf:
        # If explicit confirmations are missing (None), fall back to score-based checks.
        breakout_ok = (breakout_confirmed is True) or (breakout_confirmed is None and breakout_score >= 58.0)
        momentum_ok = (momentum_confirmed is True) or (momentum_confirmed is None and momentum_score >= 58.0)
        if not (breakout_ok and momentum_ok):
            quality_gate_rejection = (
                f"require_both_confirmations: breakout={breakout_confirmed}/{breakout_score:.1f}, "
                f"momentum={momentum_confirmed}/{momentum_score:.1f}"
            )
    if quality_gate_rejection is None and breakout_hold_confirmed is False:
        quality_gate_rejection = "breakout_hold_confirmed=false (avoid weak post-breakout entries)"
    if quality_gate_rejection is None and timing_risk == "HIGH":
        quality_gate_rejection = "timing_risk=HIGH"
    if quality_gate_rejection is None and market_bias == "WEAK_BOTH" and not (quality_score >= 90.0 and confirmation_score >= 92.0):
        quality_gate_rejection = "market_bias=WEAK_BOTH (requires very high quality override)"
    if quality_gate_rejection is None and fake_move_risk > PAPER_MAX_FAKE_MOVE_RISK:
        quality_gate_rejection = f"fake_move_risk>{PAPER_MAX_FAKE_MOVE_RISK:.1f} (got {fake_move_risk:.1f})"
    if quality_gate_rejection is None and news_risk > PAPER_MAX_NEWS_RISK:
        quality_gate_rejection = f"news_risk>{PAPER_MAX_NEWS_RISK:.1f} (got {news_risk:.1f})"
    if quality_gate_rejection is None and liquidity_spike_risk > PAPER_MAX_LIQUIDITY_SPIKE_RISK:
        quality_gate_rejection = f"liquidity_spike_risk>{PAPER_MAX_LIQUIDITY_SPIKE_RISK:.1f} (got {liquidity_spike_risk:.1f})"
    if quality_gate_rejection is None and premium_distortion > PAPER_MAX_PREMIUM_DISTORTION:
        quality_gate_rejection = f"premium_distortion>{PAPER_MAX_PREMIUM_DISTORTION:.1f} (got {premium_distortion:.1f})"
    if quality_gate_rejection is None and PAPER_MARKET_REGIME_FILTER and market_regime == "LOW_VOLATILITY":
        quality_gate_rejection = "market_regime=LOW_VOLATILITY (avoid choppy conditions)"
    if quality_gate_rejection is None and not daily_ok:
        quality_gate_rejection = daily_reason
    
    if quality_gate_rejection:
        return {
            "success": False,
            "message": "Paper trade blocked: quality gate rejected",
            "quality_gate_reason": quality_gate_rejection,
            "signal_type": "stock" if signal_is_stock else "index",
            "quality_gate_details": {
                "quality_score": round(quality_score, 2),
                "quality_minimum": quality_gate,
                "confirmation_score": round(confirmation_score, 2),
                "confirmation_minimum": confirmation_gate,
                "ai_edge_score": round(ai_edge_score, 2),
                "ai_edge_minimum": ai_edge_gate,
                "breakout_score": round(breakout_score, 2),
                "momentum_score": round(momentum_score, 2),
                "rr": rr_value_cmp,
                "rr_minimum": rr_gate,
                "breakout_confirmed": breakout_confirmed,
                "momentum_confirmed": momentum_confirmed,
                "market_regime": market_regime,
                "market_bias": market_bias,
                "timing_risk": timing_risk,
                "breakout_hold_confirmed": breakout_hold_confirmed,
                "fake_move_risk": round(fake_move_risk, 2),
                "fake_move_risk_max": PAPER_MAX_FAKE_MOVE_RISK,
                "news_risk": round(news_risk, 2),
                "news_risk_max": PAPER_MAX_NEWS_RISK,
                "liquidity_spike_risk": round(liquidity_spike_risk, 2),
                "liquidity_spike_risk_max": PAPER_MAX_LIQUIDITY_SPIKE_RISK,
                "premium_distortion": round(premium_distortion, 2),
                "premium_distortion_max": PAPER_MAX_PREMIUM_DISTORTION,
                "daily_trades_count": _paper_count_daily_trades(db),
                "max_daily_trades": PAPER_MAX_DAILY_TRADES,
                "consecutive_sl_count": _paper_count_consecutive_sl_hits(db),
                "consecutive_sl_limit": PAPER_CONSECUTIVE_SL_HIT_LIMIT,
                "daily_pnl": round(_paper_get_daily_pnl(db), 2),
                "daily_profit_target": PAPER_DAILY_PROFIT_TARGET,
            },
        }

    blocked, wait_seconds, meta = _paper_sl_cooldown_info(db, trade.symbol, trade.side)
    if blocked:
        return {
            "success": False,
            "message": "SL cooldown active for this symbol/side. Wait before re-entry.",
            "wait_seconds": wait_seconds,
            **(meta or {}),
        }

    reentry_blocked, reentry_wait_seconds, reentry_meta = _paper_recent_reentry_guard(db, trade)
    if reentry_blocked:
        return {
            "success": False,
            "message": "Same-move re-entry blocked until breakout is fresher or AI conviction improves.",
            "wait_seconds": reentry_wait_seconds,
            **(reentry_meta or {}),
        }

    open_trades = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
    active_count = len(open_trades)

    if active_count >= MAX_PAPER_TRADES:
        return {
            "success": False,
            "message": f"Cannot create new trade. {active_count} active trade(s) already exist.",
            "active_trades": active_count
        }

    # Server-side multi-tick confirmation guard (mirror live behavior)
    # Server-side multi-tick confirmation guard (mirror live behavior)
    underlying = _symbol_root(trade.symbol)
    try:
        if not getattr(trade, 'bypass_confirmation', False):
            confirmed = _require_multi_tick_confirmation(underlying, trade.entry_price, trade.side, required_ticks=3)
        else:
            confirmed = True
    except Exception:
        confirmed = False

    if not confirmed:
        return {
            "success": False,
            "message": "Paper trade blocked: failed multi-tick confirmation (server guard).",
            "underlying": underlying,
            "required_ticks": 3,
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
    
    try:
        db.add(paper_trade)
        db.commit()
        db.refresh(paper_trade)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Paper trade persistence failed: {e.__class__.__name__}")
    
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
    _backfill_paper_profit_trail_rows(db)
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
    _backfill_paper_profit_trail_rows(db)
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
