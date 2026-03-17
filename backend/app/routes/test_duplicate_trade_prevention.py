"""
Unit tests for duplicate trade prevention logic.
Tests ensure that identical OPEN trades cannot be created multiple times.

Policy:
- Duplicate check only on ACTIVE OPEN trades (NOT history)
- 5-minute cooldown after SL_HIT on same symbol/side
- Fresh quality signal required to re-enter after cooldown
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from app.routes.auto_trading_simple import _is_duplicate_trade


class TestDuplicateTradeDetection:
    """Test suite for duplicate trade prevention - ACTIVE TRADES ONLY."""

    def test_no_duplicate_when_empty_trades(self):
        """No trades exist yet - should not be marked as duplicate."""
        with patch("app.routes.auto_trading_simple.active_trades", []):
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "DEMO")
            assert not is_dup
            assert reason is None

    def test_duplicate_active_trade_same_symbol_side_mode(self):
        """Identical OPEN trade exists - should be marked duplicate."""
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "OPEN",
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "DEMO")
            assert is_dup
            assert "Active trade exists" in reason

    def test_no_duplicate_different_side(self):
        """Different side (BUY vs SELL) - should not be duplicate."""
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "OPEN",
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            is_dup, reason = _is_duplicate_trade("NIFTY", "SELL", 100.0, "DEMO")
            assert not is_dup

    def test_no_duplicate_different_symbol(self):
        """Different symbol - should not be duplicate."""
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "OPEN",
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            is_dup, reason = _is_duplicate_trade("BANKNIFTY", "BUY", 100.0, "DEMO")
            assert not is_dup

    def test_no_duplicate_different_mode(self):
        """Different mode (DEMO vs LIVE) - should not be duplicate."""
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "OPEN",
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "LIVE")
            assert not is_dup

    def test_no_duplicate_sl_hit_trade(self):
        """Trade with SL_HIT status - should not match (only OPEN checked)."""
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "SL_HIT",  # Not OPEN
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "DEMO")
            assert not is_dup, "SL_HIT trades should not block new entries (5-min cooldown handles this)"

    def test_no_duplicate_target_hit_trade(self):
        """Trade that hit target - should not block new entries."""
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "TARGET_HIT",  # Closed with profit
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "DEMO")
            assert not is_dup, "Completed trades should not block re-entry"

    def test_multiple_active_trades_finds_first_match(self):
        """Multiple active trades - should find the first matching one."""
        active_trades_list = [
            {
                "symbol": "BANKNIFTY",
                "side": "BUY",
                "price": 50.0,
                "status": "OPEN",
                "trade_mode": "DEMO"
            },
            {
                "symbol": "NIFTY",
                "side": "BUY",
                "price": 100.0,
                "status": "OPEN",
                "trade_mode": "DEMO"
            },
            {
                "symbol": "FINNIFTY",
                "side": "SELL",
                "price": 200.0,
                "status": "OPEN",
                "trade_mode": "LIVE"
            }
        ]
        
        with patch("app.routes.auto_trading_simple.active_trades", active_trades_list):
            # Should find the NIFTY BUY match
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "DEMO")
            assert is_dup
            assert "NIFTY" in reason

    def test_case_insensitive_matching(self):
        """Symbol/side matching should be case-insensitive."""
        active_trade = {
            "symbol": "nifty",
            "side": "buy",
            "price": 100.0,
            "status": "OPEN",
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            # Query with uppercase
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "DEMO")
            assert is_dup

    def test_live_and_demo_trades_separate(self):
        """LIVE and DEMO trades with same symbol/side should NOT block each other."""
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "OPEN",
            "trade_mode": "LIVE"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            # Trying to create DEMO trade while LIVE exists - should NOT be duplicate
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 100.0, "DEMO")
            assert not is_dup

    def test_sl_hit_does_not_block_new_entry(self):
        """After SL_HIT, same symbol/side should allow NEW entry (5-min cooldown instead)."""
        # This tests the core policy: duplicate check only on OPEN trades
        # SL_HIT trades are handled by cooldown system (5 minutes), not duplicate check
        active_trade = {
            "symbol": "NIFTY",
            "side": "BUY",
            "price": 100.0,
            "status": "SL_HIT",
            "trade_mode": "DEMO"
        }
        
        with patch("app.routes.auto_trading_simple.active_trades", [active_trade]):
            # Should allow new entry - SL_HIT doesn't block via duplicate check
            is_dup, reason = _is_duplicate_trade("NIFTY", "BUY", 105.0, "DEMO")
            assert not is_dup
            # The cooldown system (5 minutes) will handle preventing re-entry if within window


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
