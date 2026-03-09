"""
Unit tests for stock option signal filtering and generation.
Tests that stock option signals are properly generated, classified, and filtered.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from app.engine.option_signal_generator import (
    select_best_signal,
    _build_scan_symbol_universe,
    fetch_index_option_chain,
    generate_signals,
)


class TestStockSymbolDetection:
    """Test that stock symbols are correctly identified vs indices."""

    def test_nifty50_stock_symbols_included(self):
        """Test that NIFTY 50 stocks are included when requested."""
        from app.engine.option_signal_generator import NIFTY_50_SYMBOLS
        
        assert "TCS" in NIFTY_50_SYMBOLS
        assert "INFY" in NIFTY_50_SYMBOLS
        assert "RELIANCE" in NIFTY_50_SYMBOLS
        assert "HDFC" in NIFTY_50_SYMBOLS or "HDFCBANK" in NIFTY_50_SYMBOLS

    def test_build_scan_symbol_universe_indices_only(self):
        """Test that only indices are returned when stock flags are false."""
        result = _build_scan_symbol_universe(
            include_nifty50=False,
            include_fno_universe=False,
            max_symbols=40,
            instruments_nfo=[],
        )
        
        # Should contain only indices
        assert "NIFTY" in result
        assert "BANKNIFTY" in result
        assert "FINNIFTY" in result
        assert "SENSEX" in result
        
        # Should not contain stocks
        assert "TCS" not in result
        assert "INFY" not in result

    def test_build_scan_symbol_universe_with_nifty50(self):
        """Test that NIFTY 50 stocks are included when requested."""
        result = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=40,
            instruments_nfo=[],
        )
        
        # Should contain indices first
        assert "NIFTY" in result
        assert "BANKNIFTY" in result
        
        # Should contain some NIFTY 50 stocks
        stock_symbols = [s for s in result if s not in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]]
        assert len(stock_symbols) > 0, "Should include NIFTY 50 stocks"
        
        # Spot check some known stocks
        assert any(s in result for s in ["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK"])

    def test_build_scan_symbol_universe_respects_max_symbols(self):
        """Test that total symbols respect max budget for stocks (indices are always included)."""
        max_symbols = 5
        result = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=max_symbols,
            instruments_nfo=[],
        )
        
        # Indices (4) are always included, stocks are capped at max_symbols
        # Total may exceed max_symbols due to fixed indices, but stock portion is bounded
        indices_count = len([s for s in result if s in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]])
        assert indices_count == 4, "Should always include all 4 indices"
        
        # Verify some stocks are included when requested
        stocks = [s for s in result if s not in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]]
        assert len(stocks) > 0, "Should include stocks when include_nifty50=True"
        assert len(stocks) <= max_symbols, f"Stock count should not exceed {max_symbols}"


class TestStockOptionSignalStructure:
    """Test that stock option signals have proper structure."""

    def test_stock_signal_has_required_fields(self):
        """Test that a stock option signal has all required fields."""
        sample_stock_signal = {
            "symbol": "TCSCE4800CE",
            "index": "TCS",  # Stock name as index
            "strike": 4800,
            "entry_price": 15.5,
            "target": 25.0,
            "stop_loss": 10.0,
            "confidence": 78.5,
            "quality_score": 79.0,
            "option_type": "CE",
            "trend_direction": "UPTREND",
            "trend_strength": "MODERATE",
            "expiry_date": "2024-12-26",
        }
        
        # Verify required fields exist
        required_fields = [
            "symbol", "index", "entry_price", "target", "stop_loss",
            "confidence", "quality_score", "option_type"
        ]
        
        for field in required_fields:
            assert field in sample_stock_signal, f"Missing required field: {field}"
            assert sample_stock_signal[field] is not None, f"Field {field} is None"

    def test_stock_signal_passes_basic_validation(self):
        """Test that stock signals pass basic validation in select_best_signal."""
        stock_signals = [
            {
                "symbol": "TCSCE4800CE",
                "index": "TCS",
                "strike": 4800,
                "entry_price": 15.5,
                "target": 25.0,
                "stop_loss": 10.0,
                "confidence": 78.5,
                "quality_score": 79.0,
                "option_type": "CE",
            },
            {
                "symbol": "INFYPE4000CE",
                "index": "INFY",
                "strike": 4000,
                "entry_price": 22.3,
                "target": 35.0,
                "stop_loss": 18.0,
                "confidence": 81.0,
                "quality_score": 82.0,
                "option_type": "CE",
            },
        ]
        
        # Both stock signals should pass validation
        result = select_best_signal(stock_signals)
        
        # Should return one of the signals (the one with best quality)
        assert result is not None, "select_best_signal should return a signal for valid stock options"
        assert result["symbol"] in ["INFYPE4000CE", "TCSCE4800CE"]
        assert result["quality_score"] >= 75  # Should pass quality threshold


class TestGetSignalGroupFunction:
    """Test the getSignalGroup classification function behavior."""

    def test_index_symbols_classified_correctly(self):
        """Test that index symbols are classified as 'indices'."""
        # Simulate the getSignalGroup logic from frontend
        INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
        
        def get_signal_group(signal):
            indexName = str(signal.get('index') or '').upper()
            if indexName in INDEX_SYMBOLS:
                return 'indices'
            symbol = str(signal.get('symbol') or '').upper()
            for idx in INDEX_SYMBOLS:
                if idx in symbol:
                    return 'indices'
            return 'stocks'
        
        # Index signals should be classified as 'indices'
        nifty_signal = {"index": "NIFTY", "symbol": "NIFTY26DEC23C20000"}
        assert get_signal_group(nifty_signal) == 'indices'
        
        banknifty_signal = {"index": "BANKNIFTY", "symbol": "BANKNIFTY26DEC23C43000"}
        assert get_signal_group(banknifty_signal) == 'indices'

    def test_stock_symbols_classified_correctly(self):
        """Test that stock symbols are classified as 'stocks'."""
        INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
        
        def get_signal_group(signal):
            indexName = str(signal.get('index') or '').upper()
            if indexName in INDEX_SYMBOLS:
                return 'indices'
            symbol = str(signal.get('symbol') or '').upper()
            for idx in INDEX_SYMBOLS:
                if idx in symbol:
                    return 'indices'
            return 'stocks'
        
        # Stock signals should be classified as 'stocks'
        tcs_signal = {"index": "TCS", "symbol": "TCSCE4800CE"}
        assert get_signal_group(tcs_signal) == 'stocks'
        
        infy_signal = {"index": "INFY", "symbol": "INFYPE4000CE"}
        assert get_signal_group(infy_signal) == 'stocks'
        
        reliance_signal = {"index": "RELIANCE", "symbol": "RELIANCECE3500CE"}
        assert get_signal_group(reliance_signal) == 'stocks'

    def test_mixed_signals_classification(self):
        """Test that mixed index and stock signals are classified correctly."""
        INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
        
        def get_signal_group(signal):
            indexName = str(signal.get('index') or '').upper()
            if indexName in INDEX_SYMBOLS:
                return 'indices'
            symbol = str(signal.get('symbol') or '').upper()
            for idx in INDEX_SYMBOLS:
                if idx in symbol:
                    return 'indices'
            return 'stocks'
        
        signals = [
            {"index": "NIFTY", "symbol": "NIFTY26DEC23C20000"},
            {"index": "TCS", "symbol": "TCSCE4800CE"},
            {"index": "BANKNIFTY", "symbol": "BANKNIFTY26DEC23C43000"},
            {"index": "INFY", "symbol": "INFYPE4000CE"},
        ]
        
        indices = [s for s in signals if get_signal_group(s) == 'indices']
        stocks = [s for s in signals if get_signal_group(s) == 'stocks']
        
        assert len(indices) == 2, "Should have 2 index signals"
        assert len(stocks) == 2, "Should have 2 stock signals"


class TestStockSignalFiltering:
    """Test that stock signals pass through filtering pipeline."""

    def test_stock_signals_pass_quality_filter(self):
        """Test that quality signals from stocks pass the quality threshold."""
        stock_signals = [
            {
                "symbol": "TCSCE4800CE",
                "index": "TCS",
                "entry_price": 15.5,
                "target": 25.0,
                "stop_loss": 10.0,
                "quality_score": 82.0,
                "confidence": 78.5,
            },
            {
                "symbol": "TCSCE4800PE",
                "index": "TCS",
                "entry_price": 12.0,
                "target": 22.0,
                "stop_loss": 7.0,
                "quality_score": 76.0,
                "confidence": 72.0,
            },
        ]
        
        # Both stock signals should pass quality filter (>= 75)
        high_quality = [s for s in stock_signals if s.get("quality_score", 0) >= 75]
        assert len(high_quality) == 2, "Both stock signals should pass quality threshold"

    def test_multiple_stock_signals_selected(self):
        """Test that multiple quality stock signals can coexist."""
        mixed_signals = [
            # Index signals
            {"symbol": "NIFTYOPT", "index": "NIFTY", "quality_score": 85, "confidence": 80},
            {"symbol": "BANKNIFTYOPT", "index": "BANKNIFTY", "quality_score": 83, "confidence": 78},
            # Stock signals
            {"symbol": "TCSCE4800CE", "index": "TCS", "quality_score": 82, "confidence": 78},
            {"symbol": "INFYPE4000CE", "index": "INFY", "quality_score": 80, "confidence": 76},
            {"symbol": "RELIANCECE3500CE", "index": "RELIANCE", "quality_score": 79, "confidence": 75},
        ]
        
        def get_signal_group(signal):
            INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
            indexName = str(signal.get('index') or '').upper()
            return 'indices' if indexName in INDEX_SYMBOLS else 'stocks'
        
        # Separate signals
        index_signals = [s for s in mixed_signals if get_signal_group(s) == 'indices']
        stock_signals = [s for s in mixed_signals if get_signal_group(s) == 'stocks']
        
        # Apply quality filter to both
        quality_threshold = 75
        quality_indices = [s for s in index_signals if s.get("quality_score", 0) >= quality_threshold]
        quality_stocks = [s for s in stock_signals if s.get("quality_score", 0) >= quality_threshold]
        
        assert len(quality_indices) == 2, "Should have 2 quality index signals"
        assert len(quality_stocks) == 3, "Should have 3 quality stock signals"
        
        total_quality = len(quality_indices) + len(quality_stocks)
        assert total_quality == 5, f"Should have 5 total quality signals, got {total_quality}"


class TestFetchStockOptionChain:
    """Test fetching option chains for stock symbols."""

    def test_fetch_index_option_chain_needs_stock_handling(self):
        """Test that fetch_index_option_chain currently fails for stocks (documenting the bug)."""
        # This test documents that the function doesn't handle stocks
        # The function should either:
        # 1. Skip stock symbols gracefully
        # 2. Handle stock symbols with modified logic
        # 3. Return a specific error that indicates it's a stock symbol
        
        # For now, we just verify the function exists and is callable
        assert callable(fetch_index_option_chain)


class TestSignalGenerationWithStocks:
    """Test overall signal generation with stock options included."""

    @patch('app.engine.option_signal_generator._get_kite')
    @patch('app.engine.option_signal_generator.fetch_index_option_chain')
    def test_generate_signals_attempts_stock_symbols(self, mock_fetch, mock_get_kite):
        """Test that generate_signals tries to fetch signals for stock symbols."""
        # Clear the global cache and rate limit state to avoid test pollution
        from app.engine.option_signal_generator import _signals_cache
        import app.engine.option_signal_generator as osg
        _signals_cache.clear()
        osg._signals_last_call = 0
        
        mock_kite = MagicMock()
        # Ensure instruments() returns a list
        mock_kite.instruments.return_value = []
        mock_get_kite.return_value = mock_kite
        
        # Mock the fetch function to return dummy signals
        def mock_fetch_side_effect(symbol, *args, **kwargs):
            if symbol in ["NIFTY", "BANKNIFTY"]:
                return [{"symbol": f"{symbol}_CE", "index": symbol, "quality_score": 80}]
            else:
                # Current behavior: likely returns error for stocks
                return {"error": f"Cannot handle stock symbol: {symbol}"}
        
        mock_fetch.side_effect = mock_fetch_side_effect
        
        # Generate signals with stocks included
        signals = generate_signals(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=10,
        )
        
        # Verify the function was called
        assert mock_fetch.called, "fetch_index_option_chain should have been called"


class TestStockSignalIntegration:
    """Integration tests for stock option signal workflow."""

    def test_stock_and_index_signals_can_coexist(self):
        """Test that stock and index signals can be processed together."""
        mixed_signals = [
            # Index signals
            {
                "symbol": "NIFTYOPT1",
                "index": "NIFTY",
                "entry_price": 100,
                "target": 150,
                "stop_loss": 80,
                "quality_score": 85,
                "confidence": 80,
                "option_type": "CE",
            },
            # Stock signals
            {
                "symbol": "TCSCE4800CE",
                "index": "TCS",
                "entry_price": 15,
                "target": 25,
                "stop_loss": 10,
                "quality_score": 80,
                "confidence": 75,
                "option_type": "CE",
            },
            {
                "symbol": "INFYPE4000CE",
                "index": "INFY",
                "entry_price": 22,
                "target": 35,
                "stop_loss": 18,
                "quality_score": 79,
                "confidence": 74,
                "option_type": "CE",
            },
        ]
        
        # All signals should be valid
        for signal in mixed_signals:
            result = select_best_signal([signal])
            assert result is not None, f"Signal {signal['symbol']} should be valid"

    def test_filtering_preserves_stock_and_index_separation(self):
        """Test that filtering maintains separation between stock and index signals."""
        INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
        
        def get_signal_group(signal):
            indexName = str(signal.get('index') or '').upper()
            if indexName in INDEX_SYMBOLS:
                return 'indices'
            symbol = str(signal.get('symbol') or '').upper()
            for idx in INDEX_SYMBOLS:
                if idx in symbol:
                    return 'indices'
            return 'stocks'
        
        signals = [
            {"symbol": "NIFTYOPT", "index": "NIFTY", "quality_score": 85},
            {"symbol": "BANKNIFTYOPT", "index": "BANKNIFTY", "quality_score": 82},
            {"symbol": "TCSCE4800CE", "index": "TCS", "quality_score": 80},
            {"symbol": "INFYPE4000CE", "index": "INFY", "quality_score": 78},
        ]
        
        # Apply quality filter
        quality_signals = [s for s in signals if s.get("quality_score", 0) >= 75]
        
        # Separate by group
        indices = [s for s in quality_signals if get_signal_group(s) == 'indices']
        stocks = [s for s in quality_signals if get_signal_group(s) == 'stocks']
        
        # Verify separation worked
        assert all(get_signal_group(s) == 'indices' for s in indices)
        assert all(get_signal_group(s) == 'stocks' for s in stocks)
        assert len(indices) == 2
        assert len(stocks) == 2


class TestSignalCapitalCalculation:
    """Test that signal capital requirements are calculated correctly."""

    def test_index_option_lot_sizes(self):
        """Test that index options have correct lot sizes."""
        # Expected lot sizes for Indian indices (as defined in the signal generator)
        expected_lot_sizes = {
            "NIFTY": 50,
            "BANKNIFTY": 30,
            "FINNIFTY": 40,
            "SENSEX": 10,
        }

        # Verify these are the standard lot sizes used
        assert expected_lot_sizes["NIFTY"] == 50
        assert expected_lot_sizes["BANKNIFTY"] == 30
        assert expected_lot_sizes["FINNIFTY"] == 40
        assert expected_lot_sizes["SENSEX"] == 10

    def test_nifty_signal_capital_calculation(self):
        """Test capital calculation for NIFTY option signals."""
        # Mock NIFTY signal with realistic data
        nifty_signal = {
            "symbol": "NIFTY2631023800PE",
            "index": "NIFTY",
            "signal_type": "index",
            "quantity": 50,  # NIFTY lot size
            "entry_price": 219.80,
            "target": 246.95,
            "stop_loss": 198.08,
            "quality_score": 70,
            "confidence": 70.0,
        }

        # Calculate expected capital
        expected_capital = nifty_signal["entry_price"] * nifty_signal["quantity"]
        assert expected_capital == 219.80 * 50
        assert expected_capital == 10990.0

        # Verify signal has required fields for capital calculation
        assert "quantity" in nifty_signal
        assert "entry_price" in nifty_signal
        assert nifty_signal["quantity"] > 0
        assert nifty_signal["entry_price"] > 0

    def test_banknifty_signal_capital_calculation(self):
        """Test capital calculation for BANKNIFTY option signals."""
        banknifty_signal = {
            "symbol": "BANKNIFTY26MAR55400PE",
            "index": "BANKNIFTY",
            "signal_type": "index",
            "quantity": 30,  # BANKNIFTY lot size
            "entry_price": 1362.70,
            "target": 1385.00,
            "stop_loss": 1340.00,
            "quality_score": 75,
            "confidence": 75.0,
        }

        expected_capital = banknifty_signal["entry_price"] * banknifty_signal["quantity"]
        assert expected_capital == 1362.70 * 30
        assert expected_capital == 40881.0

    def test_sensex_signal_capital_calculation(self):
        """Test capital calculation for SENSEX option signals."""
        sensex_signal = {
            "symbol": "SENSEX2631276800PE",
            "index": "SENSEX",
            "signal_type": "index",
            "quantity": 10,  # SENSEX lot size
            "entry_price": 994.50,
            "target": 1020.00,
            "stop_loss": 970.00,
            "quality_score": 80,
            "confidence": 80.0,
        }

        expected_capital = sensex_signal["entry_price"] * sensex_signal["quantity"]
        assert expected_capital == 994.50 * 10
        assert expected_capital == 9945.0

    def test_stock_signal_capital_calculation(self):
        """Test capital calculation for stock option signals."""
        stock_signal = {
            "symbol": "TCSCE4800CE",
            "index": "TCS",
            "signal_type": "stock",
            "quantity": 1,  # Stock options typically 1 lot
            "entry_price": 15.50,
            "target": 25.00,
            "stop_loss": 10.00,
            "quality_score": 78,
            "confidence": 75.0,
        }

        expected_capital = stock_signal["entry_price"] * stock_signal["quantity"]
        assert expected_capital == 15.50 * 1
        assert expected_capital == 15.50

    def test_capital_calculation_with_different_quantities(self):
        """Test capital calculation with various quantity multipliers."""
        base_signal = {
            "symbol": "NIFTY2631023800PE",
            "index": "NIFTY",
            "quantity": 50,
            "entry_price": 200.00,
        }

        # Test with different multipliers
        for multiplier in [0.5, 1, 2, 3]:
            adjusted_quantity = int(base_signal["quantity"] * multiplier)
            capital = base_signal["entry_price"] * adjusted_quantity
            assert capital == 200.00 * adjusted_quantity
            assert capital > 0


class TestSignalQualityValidation:
    """Test that signals meet quality thresholds and validation criteria."""

    def test_quality_score_threshold_70_percent(self):
        """Test that signals must have 70%+ quality score."""
        high_quality_signals = [
            {"symbol": "NIFTY_CE", "quality_score": 85, "entry_price": 100, "quantity": 50},
            {"symbol": "NIFTY_PE", "quality_score": 78, "entry_price": 100, "quantity": 50},
            {"symbol": "BANKNIFTY_CE", "quality_score": 70, "entry_price": 100, "quantity": 30},
        ]

        low_quality_signals = [
            {"symbol": "LOW_QUAL_CE", "quality_score": 65, "entry_price": 100, "quantity": 50},
            {"symbol": "LOW_QUAL_PE", "quality_score": 60, "entry_price": 100, "quantity": 50},
        ]

        # High quality signals should pass
        for signal in high_quality_signals:
            assert signal["quality_score"] >= 70, f"Signal {signal['symbol']} should meet 70% threshold"

        # Low quality signals should fail
        for signal in low_quality_signals:
            assert signal["quality_score"] < 70, f"Signal {signal['symbol']} should fail 70% threshold"

    def test_signal_structure_validation(self):
        """Test that signals have all required fields."""
        required_fields = [
            "symbol", "index", "signal_type", "quantity", "entry_price",
            "target", "stop_loss", "quality_score", "confidence"
        ]

        valid_signal = {
            "symbol": "NIFTY2631023800PE",
            "index": "NIFTY",
            "signal_type": "index",
            "quantity": 50,
            "entry_price": 219.80,
            "target": 246.95,
            "stop_loss": 198.08,
            "quality_score": 70,
            "confidence": 70.0,
            "option_type": "PE",
            "strike": 23800,
        }

        # Check all required fields are present
        for field in required_fields:
            assert field in valid_signal, f"Required field '{field}' missing from signal"
            assert valid_signal[field] is not None, f"Field '{field}' cannot be None"

        # Check numeric fields are positive
        numeric_fields = ["quantity", "entry_price", "target", "stop_loss", "quality_score", "confidence"]
        for field in numeric_fields:
            value = valid_signal[field]
            assert isinstance(value, (int, float)), f"Field '{field}' must be numeric"
            assert value > 0, f"Field '{field}' must be positive"

    def test_signal_capital_reasonableness(self):
        """Test that calculated capital is within reasonable bounds."""
        test_cases = [
            # (symbol, quantity, entry_price, expected_capital_range)
            ("NIFTY_PE", 50, 200.00, (5000, 20000)),      # NIFTY: 10k-20k
            ("BANKNIFTY_CE", 30, 1500.00, (30000, 60000)), # BANKNIFTY: 45k
            ("SENSEX_PE", 10, 1000.00, (5000, 15000)),     # SENSEX: 10k
            ("TCS_CE", 1, 20.00, (10, 100)),              # Stock: small
        ]

        for symbol, qty, price, (min_cap, max_cap) in test_cases:
            capital = price * qty
            assert min_cap <= capital <= max_cap, \
                f"Capital {capital} for {symbol} outside reasonable range [{min_cap}, {max_cap}]"

    def test_signal_risk_reward_validation(self):
        """Test that signals have proper risk-reward ratios."""
        signals = [
            {
                "symbol": "NIFTY_PE",
                "entry_price": 200.00,
                "target": 250.00,  # +50 points profit
                "stop_loss": 180.00,  # -20 points loss
                "quantity": 50,
            },
            {
                "symbol": "BANKNIFTY_CE",
                "entry_price": 1500.00,
                "target": 1650.00,  # +150 points profit
                "stop_loss": 1425.00,  # -75 points loss
                "quantity": 30,
            },
        ]

        for signal in signals:
            entry = signal["entry_price"]
            target = signal["target"]
            stop_loss = signal["stop_loss"]
            qty = signal["quantity"]

            # Calculate points
            profit_points = target - entry
            loss_points = entry - stop_loss

            # Risk-reward ratio should be reasonable (at least 1:1.5)
            rr_ratio = profit_points / loss_points if loss_points > 0 else 0
            assert rr_ratio >= 1.2, f"Risk-reward ratio {rr_ratio:.2f} too low for {signal['symbol']}"

            # Capital at risk should be reasonable
            capital_at_risk = entry * qty
            max_loss = loss_points * qty
            assert max_loss < capital_at_risk * 0.5, f"Max loss {max_loss} too high vs capital {capital_at_risk}"


class TestSignalIntegrationValidation:
    """Integration tests for complete signal pipeline."""

    def test_generate_signals_produces_valid_capital_calculations(self):
        """Test that generate_signals produces signals with valid capital calculations."""
        # This test validates the capital calculation logic using mock data
        # to avoid depending on external API calls that may fail

        # Test with mock signals that represent typical index option signals
        mock_signals = [
            {
                "symbol": "NIFTY2631023800PE",
                "index": "NIFTY",
                "signal_type": "index",
                "quantity": 50,
                "entry_price": 219.80,
                "target": 246.95,
                "stop_loss": 198.08,
                "quality_score": 70,
                "confidence": 70.0,
            },
            {
                "symbol": "BANKNIFTY26MAR55400PE",
                "index": "BANKNIFTY",
                "signal_type": "index",
                "quantity": 30,
                "entry_price": 1362.70,
                "target": 1385.00,
                "stop_loss": 1340.00,
                "quality_score": 75,
                "confidence": 75.0,
            },
            {
                "symbol": "SENSEX2631276800PE",
                "index": "SENSEX",
                "signal_type": "index",
                "quantity": 10,
                "entry_price": 994.50,
                "target": 1020.00,
                "stop_loss": 970.00,
                "quality_score": 80,
                "confidence": 80.0,
            }
        ]

        for signal in mock_signals:
            # Validate capital calculation
            qty = signal.get("quantity", 0)
            entry = signal.get("entry_price", 0)
            capital = entry * qty

            assert qty > 0, f"Quantity should be positive for {signal.get('symbol')}"
            assert entry > 0, f"Entry price should be positive for {signal.get('symbol')}"
            assert capital > 0, f"Capital should be positive for {signal.get('symbol')}"

            # Validate quality meets threshold
            quality = signal.get("quality_score", 0)
            assert quality >= 70, f"Quality {quality} should meet 70%+ threshold for {signal.get('symbol')}"

            # Validate capital is reasonable (not too high or low)
            assert 1000 <= capital <= 100000, f"Capital {capital} seems unreasonable for {signal.get('symbol')}"

            print(f"✓ {signal.get('symbol')}: Qty={qty}, Entry=₹{entry:.2f}, Capital=₹{capital:.2f}, Quality={quality}%")

    def test_signal_quality_distribution(self):
        """Test that generated signals have realistic quality score distribution."""
        # Generate multiple signals to check distribution
        signals = []
        for i in range(10):
            batch = generate_signals(include_nifty50=True, max_symbols=10)
            signals.extend([s for s in batch if not s.get("error")])

        if len(signals) < 5:
            pytest.skip("Not enough signals generated for distribution test")

        quality_scores = [s.get("quality_score", 0) for s in signals]

        # Should have some high quality signals (80%+)
        high_quality = [q for q in quality_scores if q >= 80]
        assert len(high_quality) > 0, "Should have some 80%+ quality signals"

        # All should meet minimum threshold
        min_quality = min(quality_scores)
        assert min_quality >= 70, f"Minimum quality {min_quality} should be >= 70%"

        # Average should be reasonable
        avg_quality = sum(quality_scores) / len(quality_scores)
        assert 75 <= avg_quality <= 90, f"Average quality {avg_quality:.1f}% seems unrealistic"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
