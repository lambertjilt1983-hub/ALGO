from app.routes.auto_trading_simple import (
    _ai_entry_validation,
    _can_allow_additional_live_trade,
    _capital_guard_reasons,
    _capital_protection_profile,
    _has_live_balance_for_trade,
    _live_protection_active,
    _loss_brake_profile,
    active_trades,
    risk_config,
    state,
)


def _sample_signal() -> dict:
    return {
        "symbol": "NIFTY24JAN25000CE",
        "action": "BUY",
        "entry_price": 100.0,
        "target": 101.2,
        "stop_loss": 99.0,
        "quality_score": 73,
        "confirmation_score": 73,
        "option_type": "CE",
        "trend_direction": "UPTREND",
        "trend_strength": 0.8,
        "technical_indicators": {
            "rsi": 60,
            "macd": {"crossover": "bullish", "histogram": 0.3},
        },
        "market_regime": "TRENDING",
        "recent_candles": [
            {"open": 99.3, "high": 99.8, "low": 99.2, "close": 99.7},
            {"open": 99.7, "high": 100.1, "low": 99.6, "close": 100.0},
            {"open": 100.0, "high": 100.4, "low": 99.9, "close": 100.3},
            {"open": 100.3, "high": 100.8, "low": 100.2, "close": 100.6},
            {"open": 100.6, "high": 101.1, "low": 100.5, "close": 101.0},
        ],
    }


def test_loss_brake_profile_warn_stage_when_drawdown_rises():
    original_loss = state.get("daily_loss", 0.0)
    original_streak = state.get("consecutive_losses", 0)
    try:
        state["daily_loss"] = float(risk_config["max_daily_loss"]) * 0.5
        state["consecutive_losses"] = 1

        profile = _loss_brake_profile()

        assert profile["enabled"] is True
        assert profile["stage"] in {"WARN", "HARD"}
        assert profile["qty_multiplier"] < 1.0
        assert profile["drawdown_ratio"] >= 0.5
    finally:
        state["daily_loss"] = original_loss
        state["consecutive_losses"] = original_streak


def test_ai_entry_validation_tightens_thresholds_under_warn_loss_brake():
    signal = _sample_signal()
    warn_loss_brake = {
        "enabled": True,
        "stage": "WARN",
        "quality_boost": 4,
        "confidence_boost": 4,
        "rr_boost": 0.15,
        "qty_multiplier": 0.75,
        "block_new_entries": False,
    }

    ok, reasons, diag = _ai_entry_validation(signal, loss_brake=warn_loss_brake)

    assert ok is False
    assert any(r.startswith("quality<") for r in reasons)
    assert any(r.startswith("confidence<") for r in reasons)
    assert diag["loss_brake"]["stage"] == "WARN"


def test_ai_entry_validation_blocks_when_hard_loss_brake_active():
    signal = _sample_signal()
    hard_loss_brake = {
        "enabled": True,
        "stage": "HARD",
        "quality_boost": 8,
        "confidence_boost": 8,
        "rr_boost": 0.25,
        "qty_multiplier": 0.5,
        "block_new_entries": True,
    }

    ok, reasons, diag = _ai_entry_validation(signal, loss_brake=hard_loss_brake)

    assert ok is False
    assert "loss_brake_hard_block" in reasons
    assert diag["loss_brake"]["block_new_entries"] is True


def test_capital_protection_profile_scales_limits_from_balance():
    profile = _capital_protection_profile(50000)

    assert profile["enabled"] is True
    assert profile["profile"] == "CAPITAL_SHIELD_100"
    assert profile["daily_loss_cap"] > 0
    assert profile["per_trade_loss_cap"] > 0
    assert profile["max_position_cap"] <= 50000
    assert profile["max_portfolio_cap"] <= 50000


def test_capital_guard_reasons_blocks_when_trade_risk_exceeds_profile():
    original_loss = state.get("daily_loss", 0.0)
    try:
        state["daily_loss"] = 0.0
        profile = _capital_protection_profile(50000)
        reasons = _capital_guard_reasons(
            profile,
            capital_required=4000.0,
            potential_loss=500.0,
            capital_in_use=0.0,
        )
        assert any("per_trade_risk_exceeded" in r for r in reasons)
    finally:
        state["daily_loss"] = original_loss


def test_live_protection_active_only_when_live_armed_and_not_demo():
    original_live_armed = state.get("live_armed", True)
    original_demo = state.get("is_demo_mode", False)
    try:
        state["live_armed"] = True
        state["is_demo_mode"] = False
        assert _live_protection_active() is True

        state["live_armed"] = False
        assert _live_protection_active() is False

        state["live_armed"] = True
        state["is_demo_mode"] = True
        assert _live_protection_active() is False
    finally:
        state["live_armed"] = original_live_armed
        state["is_demo_mode"] = original_demo


def test_simultaneous_live_trade_allowed_for_high_quality_different_root():
    original_live_armed = state.get("live_armed", True)
    original_demo = state.get("is_demo_mode", False)
    try:
        state["live_armed"] = True
        state["is_demo_mode"] = False
        active_trades.clear()
        active_trades.append({"symbol": "NIFTY24JAN25000CE", "status": "OPEN"})

        candidate = {
            "symbol": "BANKNIFTY24JAN52000PE",
            "quality_score": 92,
            "confirmation_score": 91,
            "ai_edge_score": 82,
        }

        ok, reasons = _can_allow_additional_live_trade(candidate)

        assert ok is True
        assert reasons == []
    finally:
        active_trades.clear()
        state["live_armed"] = original_live_armed
        state["is_demo_mode"] = original_demo


def test_simultaneous_live_trade_blocked_for_same_root_or_low_quality():
    original_live_armed = state.get("live_armed", True)
    original_demo = state.get("is_demo_mode", False)
    try:
        state["live_armed"] = True
        state["is_demo_mode"] = False
        active_trades.clear()
        active_trades.append({"symbol": "NIFTY24JAN25000CE", "status": "OPEN"})

        candidate = {
            "symbol": "NIFTY24JAN24800PE",
            "quality_score": 70,
            "confirmation_score": 60,
            "ai_edge_score": 30,
        }

        ok, reasons = _can_allow_additional_live_trade(candidate)

        assert ok is False
        assert any("same_root_blocked" in r for r in reasons)
        assert any(r.startswith("quality<") for r in reasons)
    finally:
        active_trades.clear()
        state["live_armed"] = original_live_armed
        state["is_demo_mode"] = original_demo


def test_has_live_balance_for_trade_checks_available_balance():
    active_trades.clear()
    active_trades.append({"symbol": "NIFTY24JAN25000CE", "status": "OPEN", "price": 100.0, "quantity": 10})

    # 1000 already in use; 800 required is allowed on 2000 balance, 1200 is not.
    assert _has_live_balance_for_trade(2000.0, 800.0) is True
    assert _has_live_balance_for_trade(2000.0, 1200.0) is False

    active_trades.clear()
