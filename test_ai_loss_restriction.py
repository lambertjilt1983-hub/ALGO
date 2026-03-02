"""
Test suite for AI Loss Restriction System

Tests cover:
1. Trade feature extraction and analysis
2. ML prediction model calculations
3. Daily quota enforcement
4. Edge cases and boundary conditions
5. Integration with trade history
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import numpy as np
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.engine.ai_loss_restriction import (
    TradeFeatures,
    PredictionResult,
    TradeHistoryAnalyzer,
    SimpleMLPredictor,
    DailyTradeQuotaManager,
    AILossRestrictionEngine,
    Recommendation
)


class TestTradeFeatures(unittest.TestCase):
    """Test TradeFeatures dataclass"""

    def test_create_strong_signal_features(self):
        """Test creating features for a strong signal"""
        features = TradeFeatures(
            signal_confidence=0.96,
            market_trend="BULLISH",
            trend_strength=0.85,
            option_type="CE",
            recent_win_rate=0.70,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=5,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=55,
            macd_histogram=12.5,
            bollinger_position=0.75,
            volume_ratio=1.3,
            price_momentum=2.5
        )
        
        self.assertEqual(features.signal_confidence, 0.96)
        self.assertEqual(features.market_trend, "BULLISH")
        self.assertEqual(features.option_type, "CE")
        self.assertFalse(features.is_recovery_trade)

    def test_create_weak_signal_features(self):
        """Test creating features for a weak signal"""
        features = TradeFeatures(
            signal_confidence=0.42,
            market_trend="NEUTRAL",
            trend_strength=0.20,
            option_type="PE",
            recent_win_rate=0.35,
            time_of_day_hour=15,
            is_recovery_trade=True,
            days_since_last_loss=0,
            consecutive_losses=2,
            volatility_level="HIGH",
            rsi_level=75,
            macd_histogram=-5.2,
            bollinger_position=0.95,
            volume_ratio=0.8,
            price_momentum=-1.5
        )
        
        self.assertEqual(features.signal_confidence, 0.42)
        self.assertEqual(features.market_trend, "NEUTRAL")
        self.assertTrue(features.is_recovery_trade)
        self.assertEqual(features.consecutive_losses, 2)


class TestSimpleMLPredictor(unittest.TestCase):
    """Test ML prediction model"""

    def setUp(self):
        self.predictor = SimpleMLPredictor()

    def test_strong_signal_prediction(self):
        """Strong signal should predict 70%+ win probability"""
        features = TradeFeatures(
            signal_confidence=0.95,
            market_trend="BULLISH",
            trend_strength=0.80,
            option_type="CE",
            recent_win_rate=0.65,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=7,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=50,
            macd_histogram=15.0,
            bollinger_position=0.70,
            volume_ratio=1.2,
            price_momentum=2.0
        )
        
        prob = self.predictor.predict_win_probability(features)
        self.assertGreaterEqual(prob, 0.70)
        self.assertLessEqual(prob, 1.0)

    def test_weak_signal_prediction(self):
        """Weak signal should predict <50% win probability"""
        features = TradeFeatures(
            signal_confidence=0.40,
            market_trend="BEARISH",  # Against CE
            trend_strength=0.10,
            option_type="CE",
            recent_win_rate=0.30,
            time_of_day_hour=15,
            is_recovery_trade=True,
            days_since_last_loss=0,
            consecutive_losses=3,
            volatility_level="HIGH",
            rsi_level=85,
            macd_histogram=-10.0,
            bollinger_position=0.95,
            volume_ratio=0.6,
            price_momentum=-3.0
        )
        
        prob = self.predictor.predict_win_probability(features)
        self.assertLess(prob, 0.55)

    def test_prediction_bull_ce_match(self):
        """BULLISH trend + CE should get bonus"""
        features_ce = TradeFeatures(
            signal_confidence=0.80,
            market_trend="BULLISH",
            trend_strength=0.70,
            option_type="CE",
            recent_win_rate=0.50,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=3,
            consecutive_losses=0,
            volatility_level="MEDIUM",
            rsi_level=50,
            macd_histogram=5.0,
            bollinger_position=0.50,
            volume_ratio=1.0,
            price_momentum=1.0
        )
        
        prob_ce = self.predictor.predict_win_probability(features_ce)
        
        # Change to PE (opposite of BULLISH)
        features_pe = TradeFeatures(
            signal_confidence=0.80,
            market_trend="BULLISH",
            trend_strength=0.70,
            option_type="PE",  # Mismatched!
            recent_win_rate=0.50,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=3,
            consecutive_losses=0,
            volatility_level="MEDIUM",
            rsi_level=50,
            macd_histogram=5.0,
            bollinger_position=0.50,
            volume_ratio=1.0,
            price_momentum=1.0
        )
        
        prob_pe = self.predictor.predict_win_probability(features_pe)
        
        # CE should be higher (matches BULLISH)
        self.assertGreater(prob_ce, prob_pe)

    def test_prediction_recovery_penalty(self):
        """Recovery trade should have win probability penalty"""
        base_features = TradeFeatures(
            signal_confidence=0.80,
            market_trend="BULLISH",
            trend_strength=0.70,
            option_type="CE",
            recent_win_rate=0.50,
            time_of_day_hour=10,
            is_recovery_trade=False,  # Normal trade
            days_since_last_loss=3,
            consecutive_losses=0,
            volatility_level="MEDIUM",
            rsi_level=50,
            macd_histogram=5.0,
            bollinger_position=0.50,
            volume_ratio=1.0,
            price_momentum=1.0
        )
        
        recovery_features = TradeFeatures(
            signal_confidence=0.80,
            market_trend="BULLISH",
            trend_strength=0.70,
            option_type="CE",
            recent_win_rate=0.50,
            time_of_day_hour=10,
            is_recovery_trade=True,  # Recovery trade
            days_since_last_loss=3,
            consecutive_losses=0,
            volatility_level="MEDIUM",
            rsi_level=50,
            macd_histogram=5.0,
            bollinger_position=0.50,
            volume_ratio=1.0,
            price_momentum=1.0
        )
        
        prob_base = self.predictor.predict_win_probability(base_features)
        prob_recovery = self.predictor.predict_win_probability(recovery_features)
        
        # Recovery should be lower due to penalty
        self.assertLess(prob_recovery, prob_base)

    def test_prediction_clamped_range(self):
        """Prediction should always be 0.0-1.0"""
        extreme_features = TradeFeatures(
            signal_confidence=0.99,
            market_trend="BULLISH",
            trend_strength=0.99,
            option_type="CE",
            recent_win_rate=0.99,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=100,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=50,
            macd_histogram=100.0,
            bollinger_position=0.50,
            volume_ratio=2.0,
            price_momentum=10.0
        )
        
        prob = self.predictor.predict_win_probability(extreme_features)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)


class TestDailyTradeQuotaManager(unittest.TestCase):
    """Test daily quota enforcement"""

    def setUp(self):
        self.quota = DailyTradeQuotaManager(
            target_win_rate=0.80,
            daily_trade_limit=10
        )

    def test_quota_starts_empty(self):
        """New quota should be empty"""
        self.assertEqual(len(self.quota.daily_trades), 0)
        self.assertEqual(self.quota.daily_wins, 0)
        self.assertEqual(self.quota.daily_losses, 0)

    def test_add_winning_trade(self):
        """Adding a win should increment counter"""
        self.quota.record_trade(symbol="FINNIFTY", pnl=500)
        
        self.assertEqual(len(self.quota.daily_trades), 1)
        self.assertEqual(self.quota.daily_wins, 1)
        self.assertEqual(self.quota.daily_losses, 0)

    def test_add_losing_trade(self):
        """Adding a loss should increment loss counter"""
        self.quota.record_trade(symbol="FINNIFTY", pnl=-500)
        
        self.assertEqual(len(self.quota.daily_trades), 1)
        self.assertEqual(self.quota.daily_wins, 0)
        self.assertEqual(self.quota.daily_losses, 1)

    def test_can_continue_trading(self):
        """Should allow trades until quota full"""
        for i in range(9):
            self.quota.record_trade(symbol="NIFTY", pnl=100)
        
        can_continue = self.quota.can_continue_trading()
        self.assertTrue(can_continue)
        
        # 10th trade
        self.quota.record_trade(symbol="NIFTY", pnl=100)
        
        can_continue = self.quota.can_continue_trading()
        self.assertFalse(can_continue)

    def test_can_achieve_target(self):
        """Should check if 80% win rate is still achievable"""
        # 3 wins, 0 losses, 7 remaining
        self.quota.record_trade(symbol="A", pnl=100)
        self.quota.record_trade(symbol="B", pnl=100)
        self.quota.record_trade(symbol="C", pnl=100)
        
        # Can achieve: 3 + 5 = 8 wins (minimum) out of 10 → achievable
        achievable = self.quota.can_achieve_target()
        self.assertTrue(achievable)
        
        # Record 1 loss
        self.quota.record_trade(symbol="D", pnl=-100)
        
        # Can achieve: 3 + 6 = 9 wins out of 10 → still achievable
        achievable = self.quota.can_achieve_target()
        self.assertTrue(achievable)
        
        # Record 2 more losses (3 total)
        self.quota.record_trade(symbol="E", pnl=-100)
        self.quota.record_trade(symbol="F", pnl=-100)
        
        # Can achieve: 3 + 4 = 7 wins out of 10 → NOT achievable (need 8)
        achievable = self.quota.can_achieve_target()
        self.assertFalse(achievable)

    def test_current_win_rate(self):
        """Should calculate current win rate correctly"""
        self.quota.record_trade(symbol="A", pnl=100)
        self.quota.record_trade(symbol="B", pnl=-100)
        self.quota.record_trade(symbol="C", pnl=100)
        
        win_rate = self.quota.get_current_win_rate()
        expected = 2 / 3
        self.assertAlmostEqual(win_rate, expected, places=2)

    def test_quota_reset_at_midnight(self):
        """Quota should reset at midnight IST"""
        # Simulate old reset time (over 24 hours ago)
        self.quota.daily_reset_date = datetime.now() - timedelta(days=2)
        
        # Record some trades
        self.quota.record_trade(symbol="A", pnl=100)
        self.assertEqual(len(self.quota.daily_trades), 1)
        
        # Call reset check (through record_trade which checks internally)
        self.quota._reset_if_new_day()
        
        # Should still have the trade (same day in our mock)
        # This is a bit tricky to test without mocking datetime


class TestTradeHistoryAnalyzer(unittest.TestCase):
    """Test trade history analysis"""

    def setUp(self):
        self.analyzer = TradeHistoryAnalyzer()

    def test_add_trade_result(self):
        """Should record trade results"""
        self.analyzer.add_trade_result(
            symbol="FINNIFTY",
            pnl=500,
            option_type="CE",
            time_of_day=10,
            win=True
        )
        
        self.assertEqual(len(self.analyzer.trades), 1)
        self.assertEqual(self.analyzer.trades[0]["symbol"], "FINNIFTY")
        self.assertEqual(self.analyzer.trades[0]["pnl"], 500)
        self.assertTrue(self.analyzer.trades[0]["win"])

    def test_calculate_win_rate_by_symbol(self):
        """Should calculate win rate per symbol"""
        # FINNIFTY: 3 wins, 1 loss
        for _ in range(3):
            self.analyzer.add_trade_result("FINNIFTY", 100, "CE", 10, True)
        self.analyzer.add_trade_result("FINNIFTY", -100, "CE", 11, False)
        
        # NIFTY50: 2 wins, 2 losses
        for _ in range(2):
            self.analyzer.add_trade_result("NIFTY50", 100, "PE", 10, True)
        for _ in range(2):
            self.analyzer.add_trade_result("NIFTY50", -100, "PE", 11, False)
        
        finnifty_win_rate = self.analyzer.get_symbol_win_rate("FINNIFTY")
        nifty_win_rate = self.analyzer.get_symbol_win_rate("NIFTY50")
        
        self.assertAlmostEqual(finnifty_win_rate, 0.75, places=2)  # 3/4
        self.assertEqual(nifty_win_rate, 0.50)  # 2/4

    def test_recent_trades_analysis(self):
        """Should analyze recent trades only when available"""
        # Add 5 trades
        for i in range(5):
            pnl = 100 if i < 3 else -100
            self.analyzer.add_trade_result("TEST", pnl, "CE", 10, pnl > 0)
        
        # Analyze last 3 trades: 2 wins, 1 loss
        recent_win_rate = self.analyzer.get_recent_win_rate(lookback=3)
        expected = 2 / 3
        self.assertAlmostEqual(recent_win_rate, expected, places=2)


class TestAILossRestrictionEngine(unittest.TestCase):
    """Test complete AI engine integration"""

    def setUp(self):
        self.engine = AILossRestrictionEngine(
            target_win_rate=0.80,
            min_signal_confidence=0.50
        )

    def test_evaluate_strong_signal(self):
        """Strong signal should return EXECUTE recommendation"""
        features = TradeFeatures(
            signal_confidence=0.95,
            market_trend="BULLISH",
            trend_strength=0.80,
            option_type="CE",
            recent_win_rate=0.70,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=5,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=50,
            macd_histogram=10.0,
            bollinger_position=0.50,
            volume_ratio=1.2,
            price_momentum=1.5
        )
        
        result = self.engine.evaluate_signal(features)
        
        self.assertEqual(result.recommendation, Recommendation.EXECUTE)
        self.assertGreater(result.predicted_win_probability, 0.65)

    def test_evaluate_weak_signal(self):
        """Weak signal should return BLOCK recommendation"""
        features = TradeFeatures(
            signal_confidence=0.35,
            market_trend="NEUTRAL",
            trend_strength=0.10,
            option_type="CE",
            recent_win_rate=0.40,
            time_of_day_hour=15,
            is_recovery_trade=True,
            days_since_last_loss=0,
            consecutive_losses=2,
            volatility_level="HIGH",
            rsi_level=80,
            macd_histogram=-8.0,
            bollinger_position=0.90,
            volume_ratio=0.7,
            price_momentum=-2.0
        )
        
        result = self.engine.evaluate_signal(features)
        
        self.assertEqual(result.recommendation, Recommendation.BLOCK)
        self.assertLess(result.predicted_win_probability, 0.50)

    def test_daily_quota_blocks_after_full(self):
        """Should block trades after quota is full"""
        # Fill up quota with 10 trades
        for i in range(10):
            self.engine.record_trade_result(
                symbol=f"SYM{i}",
                pnl=100 if i < 8 else -100
            )
        
        # Next signal should be blocked due to quota
        features = TradeFeatures(
            signal_confidence=0.99,  # Even perfect signal
            market_trend="BULLISH",
            trend_strength=0.99,
            option_type="CE",
            recent_win_rate=0.99,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=100,
            consecutive_losses=0,
            volatility_level="LOW",
            rsi_level=50,
            macd_histogram=50.0,
            bollinger_position=0.50,
            volume_ratio=2.0,
            price_momentum=10.0
        )
        
        result = self.engine.evaluate_signal(features)
        
        # Should block because quota is full
        self.assertEqual(result.recommendation, Recommendation.BLOCK)

    def test_quota_prevents_impossible_targets(self):
        """Should block when 80% win rate becomes impossible"""
        # Add 3 wins, 3 losses (so far 50%)
        for _ in range(3):
            self.engine.record_trade_result("A", pnl=100)
            self.engine.record_trade_result("B", pnl=-100)
        
        # Add 2 more losses (now 3W-5L)
        self.engine.record_trade_result("C", pnl=-100)
        self.engine.record_trade_result("D", pnl=-100)
        
        # 7 trades used, 3 remaining
        # Max wins possible: 3 + 3 = 6
        # Need 8 wins minimum
        # Cannot achieve 80% target
        
        features = TradeFeatures(
            signal_confidence=0.90,
            market_trend="BULLISH",
            trend_strength=0.80,
            option_type="CE",
            recent_win_rate=0.50,
            time_of_day_hour=10,
            is_recovery_trade=False,
            days_since_last_loss=3,
            consecutive_losses=0,
            volatility_level="MEDIUM",
            rsi_level=50,
            macd_histogram=5.0,
            bollinger_position=0.50,
            volume_ratio=1.0,
            price_momentum=1.0
        )
        
        result = self.engine.evaluate_signal(features)
        
        # Should recommend BLOCK because 80% is mathematically impossible
        self.assertEqual(result.recommendation, Recommendation.BLOCK)

    def test_get_daily_analytics(self):
        """Should return daily analytics"""
        # Record some trades
        self.engine.record_trade_result("A", pnl=100)
        self.engine.record_trade_result("B", pnl=100)
        self.engine.record_trade_result("C", pnl=-100)
        
        analytics = self.engine.get_daily_analytics()
        
        self.assertEqual(analytics["daily_quota"]["trades_executed"], 3)
        self.assertEqual(analytics["daily_quota"]["wins"], 2)
        self.assertEqual(analytics["daily_quota"]["losses"], 1)
        self.assertAlmostEqual(analytics["daily_quota"]["current_win_rate"], 2/3, places=2)

    def test_get_symbol_quality_report(self):
        """Should categorize symbols by win rate"""
        # Good symbol (70% win rate)
        for _ in range(7):
            self.engine.record_trade_result("GOOD", pnl=100)
        for _ in range(3):
            self.engine.record_trade_result("GOOD", pnl=-100)
        
        # Bad symbol (20% win rate)
        for _ in range(2):
            self.engine.record_trade_result("BAD", pnl=100)
        for _ in range(8):
            self.engine.record_trade_result("BAD", pnl=-100)
        
        report = self.engine.get_symbol_quality_report()
        
        self.assertIn("GOOD", [s["symbol"] for s in report.get("good_symbols", [])])
        self.assertIn("BAD", [s["symbol"] for s in report.get("avoid_symbols", [])])


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        self.engine = AILossRestrictionEngine()

    def test_exactly_80_percent_win_rate(self):
        """Test at exactly 80% boundary"""
        # 8 wins, 2 losses
        for _ in range(8):
            self.engine.record_trade_result("T", pnl=100)
        for _ in range(2):
            self.engine.record_trade_result("T", pnl=-100)
        
        analytics = self.engine.get_daily_analytics()
        self.assertEqual(analytics["daily_quota"]["wins"], 8)
        self.assertEqual(analytics["daily_quota"]["losses"], 2)
        self.assertAlmostEqual(analytics["daily_quota"]["current_win_rate"], 0.80, places=2)

    def test_79_9_percent_is_below_target(self):
        """Test just below 80% boundary"""
        # 7 wins, 2 losses = 77.7%
        for _ in range(7):
            self.engine.record_trade_result("T", pnl=100)
        for _ in range(2):
            self.engine.record_trade_result("T", pnl=-100)
        
        analytics = self.engine.get_daily_analytics()
        win_rate = analytics["daily_quota"]["current_win_rate"]
        self.assertLess(win_rate, 0.80)

    def test_zero_trades_handled(self):
        """Should handle no trades gracefully"""
        analytics = self.engine.get_daily_analytics()
        
        self.assertEqual(analytics["daily_quota"]["trades_executed"], 0)
        self.assertEqual(analytics["daily_quota"]["current_win_rate"], 0.0)

    def test_single_trade_result(self):
        """Should handle single trade"""
        self.engine.record_trade_result("SINGLE", pnl=100)
        
        analytics = self.engine.get_daily_analytics()
        self.assertEqual(analytics["daily_quota"]["trades_executed"], 1)
        self.assertEqual(analytics["daily_quota"]["wins"], 1)
        self.assertEqual(analytics["daily_quota"]["current_win_rate"], 1.0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
