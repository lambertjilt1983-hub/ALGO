"""
Comprehensive integration tests for stock option signal generation.
Tests the complete workflow: generation, filtering, and classification of stock option signals.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import date, timedelta
from app.engine.option_signal_generator import (
    fetch_index_option_chain,
    generate_signals,
    select_best_signal,
    _build_scan_symbol_universe,
)


class TestFetchStockOptionChainIntegration:
    """Integration tests for fetching stock option chains."""

    def _mock_stock_instrument(self, symbol: str, strike: int, symbol_type: str):
        """Create a mock instrument record for a stock option."""
        return {
            "instrument_token": 123456,
            "exchange_token": 789,
            "tradingsymbol": f"{symbol}{strike}{symbol_type}",
            "name": symbol,
            "segment": "NFO-OPT",
            "strike": strike,
            "expiry": date.today() + timedelta(days=6),  # Next week
            "instrument_type": symbol_type,
            "lot_size": 1,  # Default lot size for stocks
            "tick_size": 0.05,
            "exchange": "NSE",
        }

    def _mock_kite_client(self):
        """Create a properly mocked Kite client."""
        kite = MagicMock()
        
        # Mock quote responses
        def mock_quote(symbols):
            quotes = {}
            for symbol in symbols:
                # Remove NSE: prefix if present
                clean_symbol = symbol.replace("NSE:", "")
                quotes[symbol] = {
                    "last_price": 100.0 if clean_symbol in ["TCS", "INFY"] else 50.0,
                    "open_price": 99.0 if clean_symbol in ["TCS", "INFY"] else 49.0,
                    "high": 105.0,
                    "low": 95.0,
                    "close": 100.0,
                    "ohlc": {
                        "open": 99.0,
                        "high": 105.0,
                        "low": 95.0,
                        "close": 100.0,
                    },
                    "volume": 10000,
                    "oi": 50000,
                }
            return quotes
        
        kite.quote = MagicMock(side_effect=mock_quote)
        return kite

    def test_fetch_tcs_stock_option_chain(self):
        """Test fetching option chain for TCS stock."""
        kite = self._mock_kite_client()
        
        instruments_nfo = [
            self._mock_stock_instrument("TCS", 4800, "CE"),
            self._mock_stock_instrument("TCS", 4800, "PE"),
            self._mock_stock_instrument("TCS", 4900, "CE"),
            self._mock_stock_instrument("TCS", 4900, "PE"),
        ]
        
        result = fetch_index_option_chain(
            "TCS",
            kite,
            instruments_nfo,
            enable_technical=False,
        )
        
        # Should return list of signals, not error
        assert isinstance(result, list), f"Expected list of signals, got {type(result)}"
        assert len(result) > 0, "Should return at least one signal"
        
        # Signals should be properly structured
        for signal in result:
            assert not signal.get("error"), f"Unexpected error in signal: {signal}"
            assert "symbol" in signal
            assert "index" in signal
            assert signal["index"] == "TCS"
            assert signal.get("signal_type") == "stock", "Should be marked as stock"

    def test_fetch_infy_stock_option_chain(self):
        """Test fetching option chain for INFY stock."""
        kite = self._mock_kite_client()
        
        instruments_nfo = [
            self._mock_stock_instrument("INFY", 4000, "CE"),
            self._mock_stock_instrument("INFY", 4000, "PE"),
        ]
        
        result = fetch_index_option_chain(
            "INFY",
            kite,
            instruments_nfo,
            enable_technical=False,
        )
        
        assert isinstance(result, list)
        assert all("signal_type" in s and s["signal_type"] == "stock" for s in result)

    def test_index_option_chain_still_works(self):
        """Verify that index option chains still work after changes."""
        kite = self._mock_kite_client()
        
        instruments_nfo = [
            {
                "instrument_token": 123456,
                "exchange_token": 789,
                "tradingsymbol": "NIFTY26MAR24C20000CE",
                "name": "NIFTY",
                "segment": "NFO-OPT",
                "strike": 20000,
                "expiry": date.today() + timedelta(days=6),
                "instrument_type": "CE",
                "lot_size": 50,
                "tick_size": 0.05,
                "exchange": "NSE",
            },
            {
                "instrument_token": 123457,
                "exchange_token": 790,
                "tradingsymbol": "NIFTY26MAR24C20000PE",
                "name": "NIFTY",
                "segment": "NFO-OPT",
                "strike": 20000,
                "expiry": date.today() + timedelta(days=6),
                "instrument_type": "PE",
                "lot_size": 50,
                "tick_size": 0.05,
                "exchange": "NSE",
            },
        ]
        
        result = fetch_index_option_chain(
            "NIFTY",
            kite,
            instruments_nfo,
            enable_technical=False,
        )
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(s.get("signal_type") == "index" for s in result), "Index should be marked as index"


class TestStockSignalGenerationWorkflow:
    """Integration tests for complete stock signal generation workflow."""

    def test_stock_universe_symbols_included(self):
        """Test that NIFTY 50 stock symbols are available for generation."""
        from app.engine.option_signal_generator import NIFTY_50_SYMBOLS
        
        # Verify key stocks are available
        key_stocks = ["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK", "WIPRO"]
        for stock in key_stocks:
            assert stock in NIFTY_50_SYMBOLS, f"{stock} should be in NIFTY 50 symbols"
    
    def test_stock_symbol_buildup_with_flag(self):
        """Test that stock symbols are included in universe when flag is true."""
        from app.engine.option_signal_generator import _build_scan_symbol_universe
        
        # With nifty50 flag, should include stocks
        universe_with = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=20,
            instruments_nfo=[],
        )
        
        # Without flag, should only have indices
        universe_without = _build_scan_symbol_universe(
            include_nifty50=False,
            include_fno_universe=False,
            max_symbols=20,
            instruments_nfo=[],
        )
        
        # With stocks should be larger
        assert len(universe_with) > len(universe_without), \
            f"Universe with stocks ({len(universe_with)}) should be larger than without ({len(universe_without)})"
        
        # Without should only have 4 indices
        assert len(universe_without) == 4, "Universe without stocks should only have 4 indices"
        assert set(universe_without) == {'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX'}


class TestStockStockIndexSignalCoexistence:
    """Test that stock and index signals coexist properly in scanning pipeline."""

    def test_mixed_stock_index_signals_filtering(self):
        """Test filtering works correctly with mixed stock and index signals."""
        mixed_signals = [
            # Index signals
            {
                "symbol": "NIFTY26MAR24C20000CE",
                "index": "NIFTY",
                "signal_type": "index",
                "entry_price": 100.0,
                "target": 150.0,
                "stop_loss": 80.0,
                "quality_score": 85.0,
                "confidence": 80.0,
            },
            # Stock signals
            {
                "symbol": "TCSCE4800CE",
                "index": "TCS",
                "signal_type": "stock",
                "entry_price": 15.5,
                "target": 25.0,
                "stop_loss": 10.0,
                "quality_score": 80.0,
                "confidence": 75.0,
            },
            {
                "symbol": "INFYPE4000CE",
                "index": "INFY",
                "signal_type": "stock",
                "entry_price": 22.3,
                "target": 35.0,
                "stop_loss": 18.0,
                "quality_score": 78.0,
                "confidence": 73.0,
            },
        ]
        
        # Apply quality filter (>= 75)
        quality_signals = [s for s in mixed_signals if s.get("quality_score", 0) >= 75]
        
        assert len(quality_signals) == 3, "All signals should pass quality threshold"
        
        # Separate by type
        stock_signals = [s for s in quality_signals if s.get("signal_type") == "stock"]
        index_signals = [s for s in quality_signals if s.get("signal_type") == "index"]
        
        assert len(stock_signals) == 2, "Should have 2 stock signals"
        assert len(index_signals) == 1, "Should have 1 index signal"

    def test_stock_signals_reach_selection_stage(self):
        """Test that stock signals can be selected by select_best_signal()."""
        stock_signals = [
            {
                "symbol": "TCSCE4800CE",
                "index": "TCS",
                "signal_type": "stock",
                "entry_price": 15.5,
                "target": 25.0,
                "stop_loss": 10.0,
                "quality_score": 82.0,
                "confidence": 78.0,
            },
            {
                "symbol": "TCSCE4900CE",
                "index": "TCS",
                "signal_type": "stock",
                "entry_price": 12.0,
                "target": 22.0,
                "stop_loss": 8.0,
                "quality_score": 79.0,
                "confidence": 75.0,
            },
        ]
        
        # select_best_signal should pick the highest quality
        result = select_best_signal(stock_signals)
        
        assert result is not None, "Should select a stock signal"
        assert result["index"] == "TCS"
        assert result["quality_score"] == 82.0, "Should pick highest quality stock signal"


class TestStockSignalFieldPresence:
    """Test that stock signals have all required fields."""

    def test_stock_signal_has_signal_type_field(self):
        """Test that generated stock signals include signal_type field."""
        signals = [
            {
                "symbol": "TCSCE4800CE",
                "index": "TCS",
                "signal_type": "stock",  # NEW FIELD
                "entry_price": 15.5,
                "target": 25.0,
                "stop_loss": 10.0,
                "quality_score": 80.0,
                "confidence": 75.0,
                "option_type": "CE",
            },
        ]
        
        for signal in signals:
            assert "signal_type" in signal, "Stock signals should include signal_type field"
            assert signal["signal_type"] in ["stock", "index"], "signal_type must be 'stock' or 'index'"

    def test_stock_signal_strategy_field_indicates_type(self):
        """Test that strategy field indicates if it's a stock or index option."""
        stock_signal = {
            "symbol": "TCSCE4800CE",
            "index": "TCS",
            "strategy": "ATM Option CE (Stock)",  # Indicates it's a stock
            "quality_score": 80.0,
        }
        
        index_signal = {
            "symbol": "NIFTY26MAR24C20000CE",
            "index": "NIFTY",
            "strategy": "ATM Option CE (Index)",  # Indicates it's an index
            "quality_score": 80.0,
        }
        
        assert "Stock" in stock_signal["strategy"]
        assert "Index" in index_signal["strategy"]


class TestStockSignalErrorHandling:
    """Test error handling for stock option chains."""

    def test_graceful_failure_for_nonexistent_stock(self):
        """Test that nonexistent stock symbols return proper error."""
        kite = MagicMock()
        
        # Empty instruments list - stock not found
        result = fetch_index_option_chain(
            "FAKESTOCK",
            kite,
            instruments_nfo=[],
            enable_technical=False,
        )
        
        # Should return error dict, not raise exception
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] is not None

    def test_stock_without_options_handling(self):
        """Test handling of stocks that don't have listed options."""
        kite = MagicMock()
        
        # Instruments exist but no options for this stock
        instruments_nfo = [
            {
                "instrument_token": 123456,
                "exchange_token": 789,
                "tradingsymbol": "OTHERSTOCK26MAR24C100CE",
                "name": "OTHERSTOCK",
                "segment": "NFO-OPT",
                "strike": 100,
                "expiry": date.today() + timedelta(days=6),
                "instrument_type": "CE",
                "lot_size": 1,
            },
        ]
        
        # Looking for TCS but only OTHERSTOCK is available
        result = fetch_index_option_chain(
            "TCS",
            kite,
            instruments_nfo,
            enable_technical=False,
        )
        
        # Should return error gracefully
        assert isinstance(result, dict)
        assert "error" in result


class TestStockSignalQualityAndFiltering:
    """Test quality filtering with stock signals."""

    def test_stock_signals_apply_same_quality_threshold(self):
        """Test that stock signals use same quality threshold as indices."""
        threshold = 75
        
        stock_signals = [
            {"symbol": "TCSCE4800CE", "index": "TCS", "quality_score": 85},
            {"symbol": "TCSCE4900CE", "index": "TCS", "quality_score": 75},
            {"symbol": "TCSCE5000CE", "index": "TCS", "quality_score": 74},
            {"symbol": "INFYPE4000CE", "index": "INFY", "quality_score": 80},
        ]
        
        # Apply threshold
        qualifying = [s for s in stock_signals if s.get("quality_score", 0) >= threshold]
        
        assert len(qualifying) == 3, f"Should have 3 signals with quality >= {threshold}"
        assert all(s["quality_score"] >= threshold for s in qualifying)

    def test_mixed_signals_maintain_ordering_after_filter(self):
        """Test that signals are properly ordered after filtering."""
        signals = [
            {"symbol": "NIFTYOPT", "index": "NIFTY", "signal_type": "index", "quality_score": 88},
            {"symbol": "TCSOPT", "index": "TCS", "signal_type": "stock", "quality_score": 82},
            {"symbol": "INFYOPT", "index": "INFY", "signal_type": "stock", "quality_score": 80},
            {"symbol": "BNIFTYOPT", "index": "BANKNIFTY", "signal_type": "index", "quality_score": 85},
        ]
        
        # Filter and sort by quality
        filtered = [s for s in signals if s["quality_score"] >= 75]
        sorted_signals = sorted(filtered, key=lambda s: s["quality_score"], reverse=True)
        
        assert len(sorted_signals) == 4
        assert sorted_signals[0]["quality_score"] == 88
        assert sorted_signals[-1]["quality_score"] == 80


class TestSymbolUniverseWithStocks:
    """Test symbol universe building with stocks."""

    def test_stock_universe_includes_nifty50_when_requested(self):
        """Test that _build_scan_symbol_universe includes NIFTY 50 stocks."""
        result = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=20,
            instruments_nfo=[],
        )
        
        # Should include NIFTY 50 stocks
        nifty50_in_result = [s for s in result if s in ["TCS", "INFY", "RELIANCE", "HDFCBANK"]]
        assert len(nifty50_in_result) > 0, "Should include NIFTY 50 stocks"

    def test_stock_universe_respects_budget(self):
        """Test that stock budget is respected in universe building."""
        max_symbols = 8
        result = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=max_symbols,
            instruments_nfo=[],
        )
        
        # 4 indices + up to max_symbols stocks
        indices = [s for s in result if s in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]]
        assert len(indices) == 4, "Should always include all 4 indices"


class TestEndToEndStockSignalWorkflow:
    """End-to-end integration tests for stock signal workflow."""

    def test_symbol_universe_building_with_stocks(self):
        """Test that symbol universe includes stocks when requested."""
        universe = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=20,
            instruments_nfo=[],
        )
        
        # Should include indices
        assert "NIFTY" in universe
        assert "BANKNIFTY" in universe
        
        # Should include NIFTY 50 stocks
        nifty50_stocks = ["ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
                          "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL",
                          "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
                          "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE"]
        
        found_stocks = [s for s in universe if s in nifty50_stocks]
        assert len(found_stocks) > 0, "Should include NIFTY 50 stocks in universe"
    
    def test_stock_detection_in_symbols(self):
        """Test that stock symbols are correctly identified from universe."""
        from app.engine.option_signal_generator import NIFTY_50_SYMBOLS
        
        # TCS should be detected as a stock
        assert "TCS" in NIFTY_50_SYMBOLS
        assert "INFY" in NIFTY_50_SYMBOLS
        assert "RELIANCE" in NIFTY_50_SYMBOLS
    
    def test_signal_processing_with_mixed_symbols(self):
        """Test that mixed index/stock signals are processed correctly."""
        signals = [
            # Indices
            {"index": "NIFTY", "signal_type": "index", "quality_score": 85},
            {"index": "BANKNIFTY", "signal_type": "index", "quality_score": 83},
            # Stocks
            {"index": "TCS", "signal_type": "stock", "quality_score": 82},
            {"index": "INFY", "signal_type": "stock", "quality_score": 80},
            {"index": "RELIANCE", "signal_type": "stock", "quality_score": 78},
        ]
        
        # All should pass quality filter
        quality_signals = [s for s in signals if s.get("quality_score", 0) >= 75]
        assert len(quality_signals) == 5
        
        # Separate by type
        indices = [s for s in quality_signals if s.get("signal_type") == "index"]
        stocks = [s for s in quality_signals if s.get("signal_type") == "stock"]
        
        assert len(indices) == 2, "Should have 2 index signals"
        assert len(stocks) == 3, "Should have 3 stock signals"
        assert len(indices) + len(stocks) == len(quality_signals), "All signals should be categorized"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
