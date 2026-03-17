from typing import Any, Dict, List


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_rr(entry_price: Any, target: Any, stop_loss: Any) -> float:
    entry = _to_float(entry_price)
    tgt = _to_float(target)
    sl = _to_float(stop_loss)
    risk = abs(entry - sl)
    reward = abs(tgt - entry)
    return (reward / risk) if risk > 0 else 0.0


def evaluate_advanced_ai_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Compute advanced diagnostics used for AI ranking and trade validation."""
    action = str(signal.get("action") or "BUY").upper()
    entry = _to_float(signal.get("entry_price"))
    target = _to_float(signal.get("target"))
    stop = _to_float(signal.get("stop_loss"))
    confidence = _to_float(signal.get("confirmation_score") or signal.get("confidence"))
    quality = _to_float(signal.get("quality_score") or signal.get("quality"))
    rr = compute_rr(entry, target, stop)
    market_regime = str(signal.get("market_regime") or signal.get("regime") or "UNKNOWN").upper()

    tech = signal.get("technical_indicators") or {}
    if not isinstance(tech, dict):
        tech = {}

    trend_direction = str(signal.get("trend_direction") or "").upper()
    trend_strength_raw = _to_float(signal.get("trend_strength"))
    trend_strength_norm = trend_strength_raw / 100.0 if trend_strength_raw > 1.5 else trend_strength_raw
    trend_strength_norm = _clamp(trend_strength_norm if trend_strength_norm > 0 else 0.5, 0.0, 1.0)

    rsi = _to_float(tech.get("rsi"), 50.0)
    macd = tech.get("macd") if isinstance(tech.get("macd"), dict) else {}
    macd_cross = str(macd.get("crossover") or "").lower()
    macd_hist = _to_float(macd.get("histogram"), 0.0)
    price_change_pct = abs(_to_float(signal.get("change_percent"), 0.0))

    # Execution-risk signals from news, liquidity and options premium behaviour.
    news_risk_raw = _to_float(signal.get("news_risk") or signal.get("news_impact_score") or signal.get("event_risk"), -1)
    spread_pct = _to_float(signal.get("bid_ask_spread_pct") or signal.get("spread_pct"), -1)
    volume_ratio = _to_float(tech.get("volume_ratio") or signal.get("volume_ratio"), -1)
    iv_spike = _to_float(signal.get("iv_spike_pct") or signal.get("implied_volatility_change"), -1)
    premium_distortion_hint = _to_float(signal.get("premium_distortion") or signal.get("premium_distortion_risk"), -1)

    # Regime score: stable trend + enough confidence/quality + sensible volatility proxy.
    regime_score = (
        0.45 * trend_strength_norm
        + 0.25 * _clamp(confidence / 100.0, 0.0, 1.0)
        + 0.20 * _clamp(quality / 100.0, 0.0, 1.0)
        + 0.10 * _clamp(price_change_pct / 1.5, 0.0, 1.0)
    )

    # Momentum score using RSI + MACD + directional movement.
    if action == "BUY":
        rsi_momentum = _clamp((rsi - 42.0) / 28.0, 0.0, 1.0)
        macd_momentum = 1.0 if macd_cross == "bullish" else (0.7 if macd_hist > 0 else 0.45)
    else:
        rsi_momentum = _clamp((58.0 - rsi) / 28.0, 0.0, 1.0)
        macd_momentum = 1.0 if macd_cross == "bearish" else (0.7 if macd_hist < 0 else 0.45)
    momentum_score = 0.55 * rsi_momentum + 0.30 * macd_momentum + 0.15 * _clamp(price_change_pct / 1.2, 0.0, 1.0)

    # Breakout score from support/resistance context.
    support = _to_float(signal.get("support"), 0.0)
    resistance = _to_float(signal.get("resistance"), 0.0)
    breakout_score = 0.55
    breakout_confirmed = False
    if action == "BUY" and resistance > 0 and entry > 0:
        breakout_buffer = (entry - resistance) / max(entry, 1.0)
        breakout_score = _clamp(0.55 + breakout_buffer * 140.0, 0.0, 1.0)
        breakout_confirmed = breakout_buffer >= 0.0015
    elif action == "SELL" and support > 0 and entry > 0:
        breakout_buffer = (support - entry) / max(entry, 1.0)
        breakout_score = _clamp(0.55 + breakout_buffer * 140.0, 0.0, 1.0)
        breakout_confirmed = breakout_buffer >= 0.0015

    # Candle-level fake breakout confirmation: detect close-back-in-range over last 3-5 candles.
    recent_candles = signal.get("recent_candles") or []
    close_back_in_range = False
    fake_breakout_by_candle = False
    wick_trap = False
    breakout_hold_confirmed = True
    if isinstance(recent_candles, list) and len(recent_candles) >= 3:
        last5 = recent_candles[-5:]
        parsed = []
        for c in last5:
            if not isinstance(c, dict):
                continue
            parsed.append({
                "open": _to_float(c.get("open")),
                "high": _to_float(c.get("high")),
                "low": _to_float(c.get("low")),
                "close": _to_float(c.get("close")),
            })
        if len(parsed) >= 3:
            lookback = parsed[:-2] if len(parsed) >= 4 else parsed[:-1]
            last = parsed[-1]
            range_high = max(c["high"] for c in lookback)
            range_low = min(c["low"] for c in lookback)
            last_close = last["close"]
            if action == "BUY":
                broke = any(c["high"] >= range_high * 1.001 for c in parsed[-2:-1])
                close_back_in_range = last_close <= range_high
                breakout_hold_confirmed = last_close > range_high
            else:
                broke = any(c["low"] <= range_low * 0.999 for c in parsed[-2:-1])
                close_back_in_range = last_close >= range_low
                breakout_hold_confirmed = last_close < range_low
            fake_breakout_by_candle = broke and close_back_in_range

            body = abs(last["close"] - last["open"])
            full = max(1e-6, last["high"] - last["low"])
            upper_wick = last["high"] - max(last["close"], last["open"])
            lower_wick = min(last["close"], last["open"]) - last["low"]
            if action == "BUY":
                wick_trap = upper_wick > body * 1.2 and body / full < 0.35
            else:
                wick_trap = lower_wick > body * 1.2 and body / full < 0.35

    trend_confirmed = True
    if trend_direction:
        trend_confirmed = ("UP" in trend_direction and action == "BUY") or ("DOWN" in trend_direction and action == "SELL")

    momentum_confirmed = momentum_score >= 0.50

    # Fake move risk rises with weak momentum, weak breakout, poor RR, direction mismatch, and candle traps.
    fake_move_risk = 0.20
    fake_move_risk += 0.25 * (1.0 - momentum_score)
    fake_move_risk += 0.20 * (1.0 - breakout_score)
    fake_move_risk += 0.15 * (1.0 - _clamp(rr / 1.5, 0.0, 1.0))
    fake_move_risk += 0.12 * (0.0 if trend_confirmed else 1.0)
    fake_move_risk += 0.08 * (0.0 if confidence >= 70 else 1.0)
    fake_move_risk += 0.12 * (1.0 if fake_breakout_by_candle else 0.0)
    fake_move_risk += 0.08 * (1.0 if wick_trap else 0.0)

    # Sudden-news risk: if explicit score missing, infer from sharp move + volatile regime.
    if news_risk_raw >= 0:
        sudden_news_risk = _clamp(news_risk_raw / 100.0, 0.0, 1.0)
    else:
        sudden_news_risk = 0.10 + 0.15 * _clamp(price_change_pct / 2.0, 0.0, 1.0)
        if market_regime == "VOLATILE":
            sudden_news_risk += 0.20

    # Liquidity spike/slippage risk from spread and unstable volume ratio.
    if spread_pct >= 0:
        spread_risk = _clamp(spread_pct / 1.2, 0.0, 1.0)
    else:
        spread_risk = 0.18
    if volume_ratio >= 0:
        # very low or very high volume can both hurt fills.
        volume_risk = _clamp(abs(volume_ratio - 1.0) / 1.2, 0.0, 1.0)
    else:
        volume_risk = 0.20
    liquidity_spike_risk = _clamp(0.65 * spread_risk + 0.35 * volume_risk, 0.0, 1.0)

    # Option premium distortion risk (IV spike or explicit hint).
    if premium_distortion_hint >= 0:
        premium_distortion_risk = _clamp(premium_distortion_hint / 100.0, 0.0, 1.0)
    elif iv_spike >= 0:
        premium_distortion_risk = _clamp(iv_spike / 35.0, 0.0, 1.0)
    else:
        premium_distortion_risk = _clamp(0.10 + 0.20 * _clamp(price_change_pct / 2.5, 0.0, 1.0), 0.0, 1.0)

    fake_move_risk += 0.12 * sudden_news_risk
    fake_move_risk += 0.10 * liquidity_spike_risk
    fake_move_risk += 0.10 * premium_distortion_risk
    fake_move_risk = _clamp(fake_move_risk, 0.0, 1.0)

    ai_edge_score = (
        0.28 * regime_score
        + 0.30 * momentum_score
        + 0.24 * breakout_score
        + 0.18 * _clamp(rr / 1.8, 0.0, 1.0)
        - 0.26 * fake_move_risk
    )
    ai_edge_score = _clamp(ai_edge_score, 0.0, 1.0)

    thresholds = {
        "min_ai_edge": 58.0,
        "min_momentum": 48.0,
        "min_breakout": 45.0,
        "max_fake_move_risk": 58.0,
        "min_rr": 1.08,
        "max_news_risk": 45.0,
        "max_liquidity_spike_risk": 50.0,
        "max_premium_distortion_risk": 50.0,
    }
    if market_regime == "TRENDING":
        thresholds = {
            "min_ai_edge": 53.0,
            "min_momentum": 43.0,
            "min_breakout": 42.0,
            "max_fake_move_risk": 68.0,
            "min_rr": 1.05,
            "max_news_risk": 55.0,
            "max_liquidity_spike_risk": 55.0,
            "max_premium_distortion_risk": 55.0,
        }
    elif market_regime == "RANGING":
        thresholds = {
            "min_ai_edge": 68.0,
            "min_momentum": 58.0,
            "min_breakout": 58.0,
            "max_fake_move_risk": 42.0,
            "min_rr": 1.22,
            "max_news_risk": 30.0,
            "max_liquidity_spike_risk": 35.0,
            "max_premium_distortion_risk": 35.0,
        }
    elif market_regime == "VOLATILE":
        thresholds = {
            "min_ai_edge": 66.0,
            "min_momentum": 56.0,
            "min_breakout": 58.0,
            "max_fake_move_risk": 45.0,
            "min_rr": 1.30,
            "max_news_risk": 32.0,
            "max_liquidity_spike_risk": 35.0,
            "max_premium_distortion_risk": 35.0,
        }

    reasons: List[str] = []
    if not trend_confirmed:
        reasons.append("trend_direction_mismatch")
    if not momentum_confirmed or (momentum_score * 100.0) < thresholds["min_momentum"]:
        reasons.append("low_momentum")
    if (breakout_score * 100.0) < thresholds["min_breakout"]:
        reasons.append("weak_breakout")
    if fake_breakout_by_candle:
        reasons.append("candle_close_back_in_range")
    if not breakout_hold_confirmed:
        reasons.append("breakout_not_holding")
    if wick_trap:
        reasons.append("wick_trap")
    if (fake_move_risk * 100.0) > thresholds["max_fake_move_risk"]:
        reasons.append("high_fake_move_risk")
    if (sudden_news_risk * 100.0) > thresholds["max_news_risk"]:
        reasons.append("sudden_news_risk")
    if (liquidity_spike_risk * 100.0) > thresholds["max_liquidity_spike_risk"]:
        reasons.append("liquidity_spike_risk")
    if (premium_distortion_risk * 100.0) > thresholds["max_premium_distortion_risk"]:
        reasons.append("premium_distortion_risk")
    if rr < thresholds["min_rr"]:
        reasons.append("low_rr")
    if (ai_edge_score * 100.0) < thresholds["min_ai_edge"]:
        reasons.append("low_ai_edge_score")

    entry_valid = len(reasons) == 0
    start_trade_allowed = entry_valid
    start_trade_decision = "YES" if start_trade_allowed else "NO"
    return {
        "trend_confirmed": trend_confirmed,
        "momentum_confirmed": momentum_confirmed,
        "breakout_confirmed": breakout_confirmed,
        "regime_score": round(regime_score * 100.0, 2),
        "momentum_score": round(momentum_score * 100.0, 2),
        "breakout_score": round(breakout_score * 100.0, 2),
        "fake_move_risk": round(fake_move_risk * 100.0, 2),
        "sudden_news_risk": round(sudden_news_risk * 100.0, 2),
        "liquidity_spike_risk": round(liquidity_spike_risk * 100.0, 2),
        "premium_distortion_risk": round(premium_distortion_risk * 100.0, 2),
        "ai_edge_score": round(ai_edge_score * 100.0, 2),
        "rr_score": round(_clamp(rr / 1.8, 0.0, 1.0) * 100.0, 2),
        "market_regime": market_regime,
        "thresholds": thresholds,
        "close_back_in_range": close_back_in_range,
        "fake_breakout_by_candle": fake_breakout_by_candle,
        "breakout_hold_confirmed": breakout_hold_confirmed,
        "wick_trap": wick_trap,
        "entry_valid": entry_valid,
        "start_trade_allowed": start_trade_allowed,
        "start_trade_decision": start_trade_decision,
        "entry_reasons": reasons,
    }
