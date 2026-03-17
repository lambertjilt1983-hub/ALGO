from app.routes.signal_scoring import evaluate_advanced_ai_signal


def test_advanced_scoring_marks_strong_buy_as_valid():
    signal = {
        "action": "BUY",
        "entry_price": 101.5,
        "target": 106.5,
        "stop_loss": 99.0,
        "confirmation_score": 86,
        "quality_score": 84,
        "trend_direction": "UPTREND",
        "trend_strength": 0.82,
        "resistance": 100.8,
        "technical_indicators": {
            "rsi": 63,
            "macd": {"crossover": "bullish", "histogram": 0.8},
        },
        "market_regime": "TRENDING",
        "recent_candles": [
            {"open": 99.8, "high": 100.3, "low": 99.6, "close": 100.2},
            {"open": 100.2, "high": 100.8, "low": 100.0, "close": 100.7},
            {"open": 100.7, "high": 101.0, "low": 100.6, "close": 100.95},
            {"open": 100.95, "high": 101.4, "low": 100.9, "close": 101.3},
            {"open": 101.3, "high": 101.9, "low": 101.2, "close": 101.7},
        ],
    }

    out = evaluate_advanced_ai_signal(signal)
    assert out["entry_valid"] is True
    assert out["ai_edge_score"] >= 60
    assert out["fake_move_risk"] <= 55
    assert out["momentum_confirmed"] is True


def test_advanced_scoring_rejects_likely_fake_move():
    signal = {
        "action": "BUY",
        "entry_price": 100.0,
        "target": 101.0,
        "stop_loss": 99.2,
        "confirmation_score": 62,
        "quality_score": 60,
        "trend_direction": "DOWNTREND",
        "trend_strength": 0.35,
        "resistance": 101.0,
        "technical_indicators": {
            "rsi": 46,
            "macd": {"crossover": "bearish", "histogram": -0.2},
        },
        "market_regime": "RANGING",
        "recent_candles": [
            {"open": 99.7, "high": 100.2, "low": 99.5, "close": 99.9},
            {"open": 99.9, "high": 100.1, "low": 99.6, "close": 99.8},
            {"open": 99.8, "high": 100.0, "low": 99.55, "close": 99.75},
            {"open": 99.75, "high": 100.35, "low": 99.7, "close": 100.2},
            {"open": 100.2, "high": 100.25, "low": 99.7, "close": 99.85},
        ],
    }

    out = evaluate_advanced_ai_signal(signal)
    assert out["entry_valid"] is False
    assert out["fake_move_risk"] > 55
    assert "high_fake_move_risk" in out["entry_reasons"] or "low_ai_edge_score" in out["entry_reasons"]


def test_candle_close_back_in_range_flag_is_set_for_fake_breakout():
    signal = {
        "action": "BUY",
        "entry_price": 101.0,
        "target": 103.0,
        "stop_loss": 100.0,
        "confirmation_score": 75,
        "quality_score": 74,
        "trend_direction": "UPTREND",
        "trend_strength": 0.6,
        "market_regime": "RANGING",
        "technical_indicators": {"rsi": 55, "macd": {"crossover": "bullish", "histogram": 0.1}},
        "recent_candles": [
            {"open": 100.0, "high": 100.6, "low": 99.8, "close": 100.4},
            {"open": 100.4, "high": 100.9, "low": 100.2, "close": 100.8},
            {"open": 100.8, "high": 101.0, "low": 100.5, "close": 100.7},
            {"open": 100.7, "high": 101.25, "low": 100.65, "close": 101.15},
            {"open": 101.15, "high": 101.2, "low": 100.45, "close": 100.75},
        ],
    }

    out = evaluate_advanced_ai_signal(signal)
    assert out["close_back_in_range"] is True
    assert out["fake_breakout_by_candle"] is True
    assert "candle_close_back_in_range" in out["entry_reasons"]
