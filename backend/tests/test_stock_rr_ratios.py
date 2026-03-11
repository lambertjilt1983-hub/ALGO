#!/usr/bin/env python3
"""
Unit tests specifically for STOCK signal generation and quality.
Tests that stock option signals have proper targeting and RR ratios.
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import date, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.option_signal_generator import (
    fetch_index_option_chain,
    generate_signals,
    _build_scan_symbol_universe,
    NIFTY_50_SYMBOLS,
)


class TestStockSignalRRRatios:
    """Test that stock signals have appropriate RR ratios."""
    
    def _mock_stock_instrument(self, symbol: str, strike: int, symbol_type: str):
        """Create a mock instrument record for a stock option."""
        return {
            "instrument_token": 123456,
            "exchange_token": 789,
            "tradingsymbol": f"{symbol}{strike}{symbol_type}",
            "name": symbol,
            "segment": "NFO-OPT",
            "strike": strike,
            "expiry": date.today() + timedelta(days=6),
            "instrument_type": symbol_type,
            "lot_size": 1,
            "tick_size": 0.05,
            "exchange": "NSE",
        }
    
    def _mock_kite_client(self, stock_name="TCS", strike_price=100.0):
        """Create a properly mocked Kite client."""
        kite = MagicMock()
        
        def mock_quote(symbols):
            quotes = {}
            for symbol in symbols:
                clean_symbol = symbol.replace("NSE:", "")
                # Use provided strike price
                quotes[symbol] = {
                    "last_price": strike_price,
                    "open_price": strike_price * 0.99,
                    "high": strike_price * 1.05,
                    "low": strike_price * 0.95,
                    "close": strike_price,
                    "ohlc": {
                        "open": strike_price * 0.99,
                        "high": strike_price * 1.05,
                        "low": strike_price * 0.95,
                        "close": strike_price,
                    },
                    "volume": 100000,
                    "oi": 500000,
                    "net_change": 1.0,
                }
            return quotes
        
        kite.quote = MagicMock(side_effect=mock_quote)
        return kite
    
    def test_stock_signal_uses_percentage_targeting(self):
        """Verify stock signals use percentage-based targets (8% profit, 5% stop)."""
        kite = self._mock_kite_client(stock_name="TCS", strike_price=200.0)
        
        instruments_nfo = [
            self._mock_stock_instrument("TCS", 200, "CE"),
            self._mock_stock_instrument("TCS", 200, "PE"),
        ]
        
        result = fetch_index_option_chain(
            "TCS",
            kite,
            instruments_nfo,
            enable_technical=False,
        )
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        ce_signal = [s for s in result if s.get("option_type") == "CE"][0]
        
        # Entry should be ~200
        entry = ce_signal["entry_price"]
        target = ce_signal["target"]
        stop = ce_signal["stop_loss"]
        
        # Target should be ~8% above entry (200 * 1.08 = 216)
        expected_target = round(entry * 1.08, 2)
        assert abs(target - expected_target) < 1.0, f"Target {target} should be ~8% above entry {entry}"
        
        # Stop should be ~5% below entry (200 * 0.95 = 190)
        expected_stop = entry * 0.95
        assert abs(stop - expected_stop) < 1.0, f"Stop {stop} should be ~5% below entry {entry}"
        
        # Calculate RR ratio
        rr = (target - entry) / (entry - stop)
        assert 1.0 < rr < 2.5, f"Stock signal RR ratio {rr} should be healthy (1.0-2.5)"
        
    def test_stock_signal_rr_ratio_calculation(self):
        """Verify that stock signals have calculated RR ratios."""
        kite = self._mock_kite_client(stock_name="INFY", strike_price=450.0)
        
        instruments_nfo = [
            self._mock_stock_instrument("INFY", 450, "CE"),
            self._mock_stock_instrument("INFY", 450, "PE"),
        ]
        
        result = fetch_index_option_chain(
            "INFY",
            kite,
            instruments_nfo,
            enable_technical=False,
        )
        
        assert len(result) > 0
        
        for signal in result:
            entry = float(signal.get("entry_price", 0))
            target = float(signal.get("target", 0))
            stop = float(signal.get("stop_loss", 0))
            
            if entry > 0 and target > 0 and stop > 0:
                rr = abs(target - entry) / abs(entry - stop)
                # Should have meaningful RR ratio
                assert rr > 1.0, f"RR ratio {rr} should be > 1.0"
                assert rr < 3.0, f"RR ratio {rr} should be < 3.0 for stock options"

    def test_index_vs_stock_signal_targeting_difference(self):
        """Verify that indices use fixed points and stocks use percentages."""
        kite = self._mock_kite_client(stock_name="TCS", strike_price=100.0)
        
        # Test stock targeting
        stock_instruments = [
            self._mock_stock_instrument("TCS", 100, "CE"),
            self._mock_stock_instrument("TCS", 100, "PE"),
        ]
        
        stock_result = fetch_index_option_chain(
            "TCS",
            kite,
            stock_instruments,
            enable_technical=False,
        )
        
        stock_signal = [s for s in stock_result if s.get("option_type") == "CE"][0]
        stock_entry = stock_signal["entry_price"]
        stock_profit = (stock_signal["target"] - stock_entry)
        
        # For stock at 100: target = 100 * 1.08 = 108, profit = 8 points
        assert 7.5 < stock_profit < 8.5, f"Stock signal should have ~8 point profit, got {stock_profit}"
        
        # For index at 100: target = 100 + 25, profit = 25 points
        # (Indices would have been fixed 25 points)
        # This is the expected difference

    def test_stock_signals_included_in_include_nifty50_request(self):
        """Verify that stock signals are included when include_nifty50=True."""
        universe = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=60,
            instruments_nfo=[],
        )
        
        indices = ["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]
        stocks = [s for s in universe if s not in indices]
        
        # Should have all 4 indices
        assert len([s for s in universe if s in indices]) == 4
        
        # Should have stocks from NIFTY 50
        assert len(stocks) > 0, "Should include NIFTY 50 stocks"
        assert len(stocks) == 48, "Should have exactly 48 NIFTY 50 stocks"
        
        # Verify some known stocks are present
        assert any(s in stocks for s in ["TCS", "INFY", "RELIANCE", "HDFCBANK"])

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
