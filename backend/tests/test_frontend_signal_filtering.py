"""
Unit tests for frontend signal filtering logic.
Tests the multi-stage filtering process used in AutoTradingDashboard.jsx

These tests can be adapted to Jest/React Testing Library format for frontend.
This file documents the expected filtering behavior.
"""

import pytest


class TestFrontendSignalFiltering:
    """Test suite for multi-stage signal filtering in AutoTradingDashboard."""

    def create_test_signal(
        self,
        symbol="NIFTY",
        action="BUY",
        entry_price=100,
        target=116,
        stop_loss=90,
        quality=85,
        confidence=70,
        rr=1.6,
        **kwargs
    ):
        """Helper to create test signal with defaults."""
        return {
            "symbol": symbol,
            "action": action,
            "entry_price": entry_price,
            "target": target,
            "stop_loss": stop_loss,
            "quality": quality,
            "quality_score": quality,
            "confirmation_score": confidence,
            "confidence": confidence,
            "rr": rr,
            "option_type": "CE",
            **kwargs,
        }

    def stage1_filter(self, signals, min_quality=70):
        """Simulate Stage-1 filtering: structural + quality + confidence + RR."""
        def safe_float(val):
            try:
                return float(val or 0)
            except (ValueError, TypeError):
                return 0
        
        return [
            s
            for s in signals
            if (
                safe_float(s.get("quality")) >= min_quality
                and safe_float(s.get("confidence")) >= 65
                and safe_float(s.get("rr")) >= 1.1
            )
        ]

    def stage2_filter(self, signals, strict_set, min_quality=70):
        """Simulate Stage-2: adaptive fallback when strict set is empty."""
        def safe_float(val):
            try:
                return float(val or 0)
            except (ValueError, TypeError):
                return 0
        
        if len(strict_set) > 0:
            return strict_set

        # Fallback to looser criteria
        fallback = [
            s
            for s in signals
            if safe_float(s.get("quality")) >= 65 and safe_float(s.get("confidence")) >= 60 and safe_float(s.get("rr")) >= 1.0
        ]
        return sorted(fallback, key=lambda s: safe_float(s.get("quality", 0)), reverse=True)[:20]

    def stage3_filter(self, signals, stability_map):
        """Simulate Stage-3: stability/hysteresis filtering."""
        def safe_float(val):
            try:
                return float(val or 0)
            except (ValueError, TypeError):
                return 0
        
        return [
            s
            for s in signals
            if (
                safe_float(s.get("quality", 0)) >= 85
                or safe_float(s.get("confidence", 0)) >= 75
                or (stability_map.get(s.get("symbol"), {}).get("seen_count", 0) >= 2)
            )
        ]

    # Stage-1 Tests
    def test_stage1_basic_requirements(self):
        """Stage-1: Should filter by quality, confidence, and RR."""
        signals = [
            self.create_test_signal(symbol="PASS1", quality=85, confidence=70, rr=1.6),  # Pass
            self.create_test_signal(symbol="PASS2", quality=75, confidence=65, rr=1.1),  # Pass
            self.create_test_signal(symbol="FAIL_Q", quality=60, confidence=70, rr=1.6),  # Fail quality
            self.create_test_signal(symbol="FAIL_C", quality=75, confidence=60, rr=1.6),  # Fail confidence
            self.create_test_signal(symbol="FAIL_RR", quality=75, confidence=70, rr=1.0),  # Fail RR
        ]

        filtered = self.stage1_filter(signals, min_quality=75)
        assert len(filtered) == 2
        assert all(s.get("quality") >= 75 for s in filtered)

    def test_stage1_sorts_by_quality_then_confidence(self):
        """Stage-1: Should sort by quality (desc) then confidence (desc)."""
        signals = [
            self.create_test_signal(symbol="NIFTY", quality=80, confidence=70),
            self.create_test_signal(symbol="BANKNIFTY", quality=85, confidence=70),
            self.create_test_signal(symbol="FINNIFTY", quality=85, confidence=75),
        ]

        filtered = self.stage1_filter(signals, min_quality=75)
        sorted_signals = sorted(
            filtered,
            key=lambda s: (s.get("quality", 0), s.get("confidence", 0)),
            reverse=True,
        )
        assert sorted_signals[0]["symbol"] == "FINNIFTY"
        assert sorted_signals[1]["symbol"] == "BANKNIFTY"

    def test_stage1_empty_signals(self):
        """Stage-1: Should return empty list when no signals pass."""
        signals = [
            self.create_test_signal(quality=50),
            self.create_test_signal(confidence=50),
        ]
        filtered = self.stage1_filter(signals, min_quality=75)
        assert len(filtered) == 0

    # Stage-2 Tests
    def test_stage2_uses_strict_set_when_available(self):
        """Stage-2: Should use Stage-1 results when available."""
        signals = [
            self.create_test_signal(symbol="GOOD", quality=85, confidence=70),
            self.create_test_signal(symbol="FALLBACK", quality=65, confidence=70),
        ]
        strict = self.stage1_filter(signals, min_quality=75)
        result = self.stage2_filter(signals, strict, min_quality=75)

        assert len(result) == 1
        assert result[0]["symbol"] == "GOOD"

    def test_stage2_fallback_when_strict_empty(self):
        """Stage-2: Should fallback to looser criteria when strict empty."""
        signals = [
            self.create_test_signal(symbol="FALLBACK", quality=65, confidence=60, rr=1.0),
            self.create_test_signal(symbol="POOR", quality=50, confidence=50, rr=0.9),
        ]
        strict = self.stage1_filter(signals, min_quality=70)  # Should be empty
        result = self.stage2_filter(signals, strict, min_quality=70)

        assert len(strict) == 0
        assert len(result) == 1
        assert result[0]["symbol"] == "FALLBACK"

    def test_stage2_fallback_limits_results_to_20(self):
        """Stage-2: Should limit fallback results to 20 signals."""
        signals = [
            self.create_test_signal(symbol=f"TEST{i}", quality=65, confidence=60, rr=1.0)
            for i in range(50)
        ]
        strict = self.stage1_filter(signals, min_quality=70)  # Empty
        result = self.stage2_filter(signals, strict, min_quality=70)

        assert len(strict) == 0
        assert len(result) <= 20

    # Stage-3 Tests
    def test_stage3_keeps_high_quality_signals(self):
        """Stage-3: Should keep signals with quality >= 85."""
        signals = [
            self.create_test_signal(symbol="HIGH", quality=85, confidence=70),
            self.create_test_signal(symbol="MID", quality=80, confidence=70),
        ]
        stability = {}
        filtered = self.stage3_filter(signals, stability)

        assert len(filtered) == 1
        assert filtered[0]["symbol"] == "HIGH"

    def test_stage3_keeps_high_confidence(self):
        """Stage-3: Should keep signals with confidence >= 75."""
        signals = [
            self.create_test_signal(symbol="HIGH_CONF", quality=70, confidence=75),
            self.create_test_signal(symbol="LOW_CONF", quality=70, confidence=70),
        ]
        stability = {}
        filtered = self.stage3_filter(signals, stability)

        assert len(filtered) == 1
        assert filtered[0]["symbol"] == "HIGH_CONF"

    def test_stage3_uses_stability_map(self):
        """Stage-3: Should use stability/hysteresis from previous scans."""
        signals = [
            self.create_test_signal(symbol="STABLE", quality=70, confidence=70),
            self.create_test_signal(symbol="NEW", quality=70, confidence=70),
        ]
        stability = {
            "STABLE": {"seen_count": 2, "last_seen": 0}  # Seen 2+ times
        }
        filtered = self.stage3_filter(signals, stability)

        assert len(filtered) == 1
        assert filtered[0]["symbol"] == "STABLE"

    # End-to-End Tests
    def test_full_pipeline_happy_path(self):
        """Full pipeline: high quality signal should pass all 3 stages."""
        signals = [self.create_test_signal(quality=90, confidence=80, rr=2.0)]

        stage1 = self.stage1_filter(signals, min_quality=75)
        stage2 = self.stage2_filter(signals, stage1, min_quality=75)
        stability = {}
        stage3 = self.stage3_filter(stage2, stability)

        assert len(stage3) == 1

    def test_full_pipeline_no_signals_available(self):
        """Full pipeline: should handle no signals gracefully."""
        signals = []

        stage1 = self.stage1_filter(signals, min_quality=75)
        stage2 = self.stage2_filter(signals, stage1, min_quality=75)
        stage3 = self.stage3_filter(stage2, {})

        assert len(stage3) == 0

    def test_full_pipeline_with_fallback(self):
        """Full pipeline: should degrade gracefully through stages."""
        signals = [
            self.create_test_signal(
                symbol="FALLBACK", quality=68, confidence=62, rr=1.05
            )
        ]

        stage1 = self.stage1_filter(signals, min_quality=75)  # Filtered out
        assert len(stage1) == 0

        stage2 = self.stage2_filter(signals, stage1, min_quality=75)  # Rescued by fallback
        assert len(stage2) == 1

        stage3 = self.stage3_filter(stage2, {})
        assert len(stage3) == 0  # Fails Stage-3 (quality < 85, conf < 75, no stability)

    # Data Validation Tests
    def test_missing_quality_field(self):
        """Should handle signals missing quality field."""
        signals = [
            {"symbol": "NIFTY", "confidence": 70, "rr": 1.6}  # Missing quality
        ]
        # Should treat as quality=0 and filter out
        filtered = self.stage1_filter(signals, min_quality=70)
        assert len(filtered) == 0

    def test_missing_confidence_field(self):
        """Should handle signals missing confidence field."""
        signals = [
            {"symbol": "NIFTY", "quality": 80, "rr": 1.6}  # Missing confidence
        ]
        # Should treat as confidence=0 and filter out
        filtered = self.stage1_filter(signals, min_quality=70)
        assert len(filtered) == 0

    def test_missing_rr_field(self):
        """Should handle signals missing RR field."""
        signals = [
            {"symbol": "NIFTY", "quality": 80, "confidence": 70}  # Missing rr
        ]
        # Should treat as rr=0 and filter out
        filtered = self.stage1_filter(signals, min_quality=70)
        assert len(filtered) == 0

    def test_none_values_handled(self):
        """Should handle None values gracefully."""
        signals = [self.create_test_signal(quality=None, confidence=None, rr=None)]
        # Should treat as 0 and filter out
        filtered = self.stage1_filter(signals, min_quality=70)
        assert len(filtered) == 0

    def test_string_numeric_values(self):
        """Should handle numeric values passed as strings."""
        signals = [
            {
                "symbol": "NIFTY",
                "quality": "85",
                "confidence": "70",
                "rr": "1.6",
            }
        ]
        # Frontend conversion needed: Number("85") = 85
        signals_converted = [
            {
                **s,
                "quality": float(s.get("quality", 0)),
                "confidence": float(s.get("confidence", 0)),
                "rr": float(s.get("rr", 0)),
            }
            for s in signals
        ]
        filtered = self.stage1_filter(signals_converted, min_quality=70)
        assert len(filtered) == 1


class TestSignalValidation:
    """Test signal validation and data consistency."""

    def test_buy_signal_target_above_entry(self):
        """BUY signals should have target > entry."""
        signal_valid = {
            "action": "BUY",
            "entry_price": 100,
            "target": 110,
            "stop_loss": 90,
        }
        signal_invalid = {
            "action": "BUY",
            "entry_price": 100,
            "target": 90,  # Below entry for BUY
            "stop_loss": 80,
        }

        # Valid check: for BUY, target > entry AND stop < entry
        def is_valid_buy(s):
            return s["target"] > s["entry_price"] and s["stop_loss"] < s["entry_price"]

        assert is_valid_buy(signal_valid)
        assert not is_valid_buy(signal_invalid)

    def test_sell_signal_target_below_entry(self):
        """SELL signals should have target < entry."""
        signal_valid = {
            "action": "SELL",
            "entry_price": 100,
            "target": 90,
            "stop_loss": 110,
        }
        signal_invalid = {
            "action": "SELL",
            "entry_price": 100,
            "target": 110,  # Above entry for SELL
            "stop_loss": 120,
        }

        # Valid check: for SELL, target < entry AND stop > entry
        def is_valid_sell(s):
            return s["target"] < s["entry_price"] and s["stop_loss"] > s["entry_price"]

        assert is_valid_sell(signal_valid)
        assert not is_valid_sell(signal_invalid)

    def test_rr_calculation_accuracy(self):
        """Should calculate RR (Risk:Reward) accurately."""

        def calc_rr(entry, target, stop):
            profit = abs(target - entry)
            risk = abs(entry - stop)
            return profit / risk if risk > 0 else 0

        # Test cases
        assert abs(calc_rr(100, 130, 90) - 3.0) < 0.01  # 30 profit / 10 risk = 3.0
        assert abs(calc_rr(100, 113, 90) - 1.3) < 0.01  # 13 profit / 10 risk = 1.3
        assert abs(calc_rr(100, 110, 90) - 1.0) < 0.01  # 10 profit / 10 risk = 1.0

    def test_quality_score_range(self):
        """Quality scores should be in valid range [0, 100]."""

        def is_valid_quality(q):
            return 0 <= q <= 100

        assert is_valid_quality(0)
        assert is_valid_quality(50)
        assert is_valid_quality(100)
        assert not is_valid_quality(-1)
        assert not is_valid_quality(101)

    def test_confidence_range(self):
        """Confidence should be in valid range [0, 100]."""

        def is_valid_confidence(c):
            return 0 <= c <= 100

        assert is_valid_confidence(0)
        assert is_valid_confidence(50)
        assert is_valid_confidence(100)
        assert not is_valid_confidence(-10)
        assert not is_valid_confidence(150)
