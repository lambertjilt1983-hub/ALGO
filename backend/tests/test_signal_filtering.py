"""
Unit tests for signal filtering functions.
Tests quality scoring, risk-reward filtering, and best signal selection.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app.engine.option_signal_generator import select_best_signal


class TestSelectBestSignal:
    """Test suite for select_best_signal function."""

    def test_empty_signals_list(self):
        """Should return None when no signals provided."""
        result = select_best_signal([])
        assert result is None

    def test_none_input(self):
        """Should return None when None is passed."""
        result = select_best_signal(None)
        assert result is None

    def test_all_error_signals(self):
        """Should return None when all signals have errors."""
        signals = [
            {"error": "API failure", "symbol": "NIFTY"},
            {"error": "No data", "symbol": "BANKNIFTY"},
        ]
        result = select_best_signal(signals)
        assert result is None

    def test_signals_missing_required_fields(self):
        """Should filter out signals missing symbol or entry_price."""
        signals = [
            {"symbol": "NIFTY"},  # missing entry_price
            {"entry_price": 100},  # missing symbol
            {"symbol": None, "entry_price": 100},  # symbol is None
            {"symbol": "NIFTY", "entry_price": None},  # entry_price is None
            {"symbol": "NIFTY", "entry_price": 0},  # entry_price is 0 (invalid)
        ]
        result = select_best_signal(signals)
        assert result is None

    def test_high_quality_signal_selection(self):
        """Should select signal with quality >= 85."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 110,
                "stop_loss": 95,
                "quality_score": 85,
                "confidence": 70,
            },
            {
                "symbol": "BANKNIFTY",
                "entry_price": 100,
                "target": 110,
                "stop_loss": 95,
                "quality_score": 75,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "NIFTY"
        assert result["quality_score"] == 85

    def test_fallback_to_75_quality(self):
        """Should use 75+ quality signals if no 85+ available."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 110,
                "stop_loss": 95,
                "quality_score": 75,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["quality_score"] == 75

    def test_rejects_below_75_quality(self):
        """Should reject signals with quality < 75."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 110,
                "stop_loss": 95,
                "quality_score": 74,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is None

    def test_risk_reward_filtering_good_ratio(self):
        """Should accept signal with RR >= 1.3."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 113,  # profit = 13
                "stop_loss": 90,  # risk = 10, RR = 1.3
                "quality_score": 80,
                "confidence": 70,
                "option_type": "CE",
                "action": "BUY",
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "NIFTY"

    def test_risk_reward_filtering_poor_ratio(self):
        """Should still accept signal with RR < 1.3 if quality is good (relaxed fallback)."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 111,  # profit = 11
                "stop_loss": 90,  # risk = 10, RR = 1.1
                "quality_score": 80,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        # Even though RR < 1.3, quality >= 75, so signal is accepted via fallback
        assert result is not None
        assert result["symbol"] == "NIFTY"

    def test_best_by_quality_score(self):
        """Should select signal with highest quality when both have good RR."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,  # RR = 1.6
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
            {
                "symbol": "BANKNIFTY",
                "entry_price": 100,
                "target": 116,  # RR = 1.6
                "stop_loss": 90,
                "quality_score": 90,  # higher quality
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "BANKNIFTY"
        assert result["quality_score"] == 90

    def test_tiebreak_by_confidence(self):
        """Should tiebreak by confidence when quality is same."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
            {
                "symbol": "BANKNIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 75,  # higher confidence
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "BANKNIFTY"
        assert result["confidence"] == 75

    def test_missing_confidence_defaults_to_zero(self):
        """Should handle missing confidence field gracefully."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                # confidence missing
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "NIFTY"

    def test_missing_quality_score_defaults_to_zero(self):
        """Should handle missing quality_score field gracefully."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "confidence": 70,
                # quality_score missing
            },
        ]
        result = select_best_signal(signals)
        assert result is None  # quality defaults to 0, which is < 75

    def test_sell_signal_rr_calculation(self):
        """Should correctly handle SELL signals in RR calculation."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 87,  # target below entry (SELL signal)
                "stop_loss": 110,  # SL above entry
                "quality_score": 85,
                "confidence": 70,
                "action": "SELL",
                "option_type": "PE",
            },
        ]
        result = select_best_signal(signals)
        # RR = |100-87| / |100-110| = 13/10 = 1.3
        assert result is not None
        assert result["symbol"] == "NIFTY"

    def test_zero_risk_stops_infinite_rr(self):
        """Should handle zero risk (target == entry) gracefully."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 100,  # same as entry (zero profit)
                "stop_loss": 95,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        # Quality is high (85) so signal passes, though RR is 0
        # This is handled by relaxed fallback: if no 1.3+ RR signals, use quality-filtered ones anyway
        assert result is not None
        assert result["symbol"] == "NIFTY"

    def test_floating_point_prices(self):
        """Should handle floating point entry/target/SL correctly."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100.50,
                "target": 116.65,  # RR = 16.15 / 10.50 = 1.538
                "stop_loss": 90.00,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "NIFTY"

    def test_string_numeric_values(self):
        """Should handle numeric values passed as strings."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": "100",
                "target": "116",
                "stop_loss": "90",
                "quality_score": "85",
                "confidence": "70",
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "NIFTY"

    def test_preserves_all_signal_fields(self):
        """Should return all fields from selected signal."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
                "action": "BUY",
                "option_type": "CE",
                "expiry_date": "2026-03-12",
            },
        ]
        result = select_best_signal(signals)
        assert result["action"] == "BUY"
        assert result["option_type"] == "CE"
        assert result["expiry_date"] == "2026-03-12"

    def test_large_signal_set_performance(self):
        """Should handle large signal sets efficiently."""
        signals = [
            {
                "symbol": f"TEST{i}",
                "entry_price": 100 + i,
                "target": 116 + i,
                "stop_loss": 90 + i,
                "quality_score": 75 + (i % 25),
                "confidence": 60 + (i % 40),
            }
            for i in range(100)
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"].startswith("TEST")

    def test_negative_prices_filtered(self):
        """Should handle negative prices gracefully."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": -100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        # Negative entry price should be filtered out
        assert result is None

    def test_special_characters_in_symbol(self):
        """Should handle symbols with special characters."""
        signals = [
            {
                "symbol": "NIFTY-2024",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "NIFTY-2024"

    def test_whitespace_in_symbol(self):
        """Should handle symbols with whitespace."""
        signals = [
            {
                "symbol": "  NIFTY  ",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        # Whitespace should not affect selection
        assert result is not None


class TestSignalReturnConsistency:
    """Test that signals are returned consistently with all required fields."""

    def test_selected_signal_has_all_required_fields(self):
        """Selected signal should contain all required trading fields."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)

        required_fields = ["symbol", "entry_price", "target", "stop_loss"]
        for field in required_fields:
            assert field in result
            assert result[field] is not None

    def test_quality_and_confidence_returned(self):
        """Quality score and confidence should be in result."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert "quality_score" in result
        assert result["quality_score"] == 85
        assert "confidence" in result
        assert result["confidence"] == 70


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_quality_exactly_85_threshold(self):
        """Should include quality_score of exactly 85."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None

    def test_quality_84_falls_to_fallback(self):
        """Should accept quality 84 via fallback to 75+ tier."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100,
                "target": 116,
                "stop_loss": 90,
                "quality_score": 84,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        # Quality 84 >= 75 (fallback threshold), so it should be accepted
        assert result is not None
        assert result["quality_score"] == 84

    def test_rr_exactly_1_3_threshold(self):
        """Should include RR of exactly 1.3."""
        signals = [
            {
                "symbol": "NIFTY",
                "entry_price": 100.0,
                "target": 113.0,  # RR = 13/10 = 1.3
                "stop_loss": 90.0,
                "quality_score": 85,
                "confidence": 70,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None

    def test_mixed_valid_invalid_signals(self):
        """Should filter invalid and select best from valid."""
        signals = [
            {"error": "API error", "symbol": "NIFTY"},
            {
                "symbol": "INVALID",
                "entry_price": 100,
                "target": 111,  # RR = 1.1 (too low)
                "stop_loss": 90,
                "quality_score": 80,
                "confidence": 70,
            },
            {
                "symbol": "GOOD",
                "entry_price": 100,
                "target": 130,  # RR = 3.0
                "stop_loss": 90,
                "quality_score": 90,
                "confidence": 75,
            },
        ]
        result = select_best_signal(signals)
        assert result is not None
        assert result["symbol"] == "GOOD"
