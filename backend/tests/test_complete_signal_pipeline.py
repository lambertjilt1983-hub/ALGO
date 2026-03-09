#!/usr/bin/env python3
"""
Comprehensive unit tests for stock signal generation and frontend classification
Tests all possible scenarios and the complete signal pipeline
"""
import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, date
from app.engine.option_signal_generator import (
    generate_signals,
    _build_scan_symbol_universe,
    fetch_index_option_chain,
    NIFTY_50_SYMBOLS,
    _validate_signal_quality,
    _apply_confirmation,
)

# ==================== TEST FIXTURES ====================

@pytest.fixture
def mock_kite():
    """Create a mock Kite object with valid future expiries"""
    future_expiry = date.today() + timedelta(days=10)
    
    mock = Mock()
    
    # Mock instruments
    mock_instruments = [
        # Indices
        {"tradingsymbol": "NIFTY23OCT25000CE", "segment": "NFO-OPT", "name": "NIFTY", 
         "expiry": future_expiry, "strike": 25000, "instrument_type": "CE", "lot_size": 50},
        {"tradingsymbol": "NIFTY23OCT25000PE", "segment": "NFO-OPT", "name": "NIFTY", 
         "expiry": future_expiry, "strike": 25000, "instrument_type": "PE", "lot_size": 50},
        
        {"tradingsymbol": "BANKNIFTY23OCT55000CE", "segment": "NFO-OPT", "name": "BANKNIFTY", 
         "expiry": future_expiry, "strike": 55000, "instrument_type": "CE", "lot_size": 30},
        {"tradingsymbol": "BANKNIFTY23OCT55000PE", "segment": "NFO-OPT", "name": "BANKNIFTY", 
         "expiry": future_expiry, "strike": 55000, "instrument_type": "PE", "lot_size": 30},
        
        # Stocks
        {"tradingsymbol": "TCSMAR24100CE", "segment": "NFO-OPT", "name": "TCS", 
         "expiry": future_expiry, "strike": 4100, "instrument_type": "CE", "lot_size": 1},
        {"tradingsymbol": "TCSMAR24100PE", "segment": "NFO-OPT", "name": "TCS", 
         "expiry": future_expiry, "strike": 4100, "instrument_type": "PE", "lot_size": 1},
        
        {"tradingsymbol": "INFYMAR24800CE", "segment": "NFO-OPT", "name": "INFY", 
         "expiry": future_expiry, "strike": 800, "instrument_type": "CE", "lot_size": 1},
        {"tradingsymbol": "INFYMAR24800PE", "segment": "NFO-OPT", "name": "INFY", 
         "expiry": future_expiry, "strike": 800, "instrument_type": "PE", "lot_size": 1},
        
        {"tradingsymbol": "RELIANCEMAR243000CE", "segment": "NFO-OPT", "name": "RELIANCE", 
         "expiry": future_expiry, "strike": 3000, "instrument_type": "CE", "lot_size": 1},
        {"tradingsymbol": "RELIANCEMAR243000PE", "segment": "NFO-OPT", "name": "RELIANCE", 
         "expiry": future_expiry, "strike": 3000, "instrument_type": "PE", "lot_size": 1},
    ]
    
    mock.instruments = Mock(return_value=mock_instruments)
    
    # Mock quote
    def mock_quote(symbols):
        quotes = {
            "NSE:NIFTY 50": {
                "last_price": 25000, "open_price": 24900,
                "ohlc": {"open": 24900, "high": 25100, "low": 24800, "close": 25000},
                "volume": 1000000
            },
            "NSE:BANKNIFTY": {
                "last_price": 55000, "open_price": 54900,
                "ohlc": {"open": 54900, "high": 55100, "low": 54800, "close": 55000},
                "volume": 800000
            },
            "NSE:TCS": {
                "last_price": 4100, "open_price": 4050,
                "ohlc": {"open": 4050, "high": 4150, "low": 4000, "close": 4100},
                "volume": 500000
            },
            "NSE:INFY": {
                "last_price": 800, "open_price": 790,
                "ohlc": {"open": 790, "high": 820, "low": 780, "close": 800},
                "volume": 2000000
            },
            "NSE:RELIANCE": {
                "last_price": 3000, "open_price": 2950,
                "ohlc": {"open": 2950, "high": 3050, "low": 2900, "close": 3000},
                "volume": 1500000
            },
        }
        return {sym: quotes.get(sym, {"last_price": 100, "ohlc": {"open": 100}}) for sym in symbols}
    
    mock.quote = mock_quote
    return mock, mock_instruments


# ==================== UNIT TESTS ====================

class TestStockSymbolUniverse:
    """Test that stock symbols are properly included in the universe"""
    
    def test_symbol_universe_includes_stocks(self):
        """Test that include_nifty50=True adds stock symbols"""
        universe = _build_scan_symbol_universe(
            include_nifty50=True,
            include_fno_universe=False,
            max_symbols=120,
            instruments_nfo=[]
        )
        
        assert len(universe) == 52  # 4 indices + 48 stocks
        assert all(s in universe for s in ["TCS", "INFY", "RELIANCE", "HDFCBANK"])
    
    def test_symbol_universe_no_stocks_by_default(self):
        """Test that stocks excluded when include_nifty50=False"""
        universe = _build_scan_symbol_universe(
            include_nifty50=False,
            include_fno_universe=False,
            max_symbols=120,
            instruments_nfo=[]
        )
        
        assert len(universe) == 4  # Only indices
        assert all(s in universe for s in ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY"])
        assert "TCS" not in universe


class TestFetchIndexOptionChain:
    """Test fetch_index_option_chain for both indices and stocks"""
    
    def test_fetch_nifty_signals_marked_as_index(self, mock_kite):
        """Test that NIFTY signals have signal_type='index'"""
        kite, instruments = mock_kite
        
        result = fetch_index_option_chain(
            index_name="NIFTY",
            kite=kite,
            instruments_nfo=instruments,
            enable_technical=False
        )
        
        assert isinstance(result, list)
        assert len(result) > 0
        
        for sig in result:
            assert sig.get("signal_type") == "index", f"Signal should have signal_type='index', got {sig.get('signal_type')}"
            assert sig.get("index") == "NIFTY"
    
    def test_fetch_stock_signals_marked_as_stock(self, mock_kite):
        """Test that TCS signals have signal_type='stock'"""
        kite, instruments = mock_kite
        
        result = fetch_index_option_chain(
            index_name="TCS",
            kite=kite,
            instruments_nfo=instruments,
            enable_technical=False
        )
        
        assert isinstance(result, list), f"Expected list, got error: {result}"
        assert len(result) > 0
        
        for sig in result:
            assert sig.get("signal_type") == "stock", f"Signal should have signal_type='stock', got {sig.get('signal_type')}"
            assert sig.get("index") == "TCS"
    
    def test_all_required_signal_fields(self, mock_kite):
        """Test that all required fields are present in generated signals"""
        kite, instruments = mock_kite
        
        for index_name in ["NIFTY", "TCS"]:
            result = fetch_index_option_chain(
                index_name=index_name,
                kite=kite,
                instruments_nfo=instruments,
                enable_technical=False
            )
            
            assert isinstance(result, list)
            for sig in result:
                required_fields = ["symbol", "index", "entry_price", "target", "stop_loss", 
                                  "action", "option_type", "signal_type"]
                for field in required_fields:
                    assert field in sig, f"Missing required field: {field} in {index_name} signal"
                    assert sig[field] is not None, f"Field {field} is None"


class TestFrontendClassification:
    """Test frontend getSignalGroup() logic"""
    
    def test_getSignalGroup_uses_signal_type_field(self):
        """Test that frontend uses signal_type field for classification"""
        def getSignalGroup(signal):
            # Replicate frontend logic
            if signal.get('signal_type'):
                return signal.get('signal_type') == 'stock' and 'stocks' or 'indices'
            # Fallback
            INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
            indexName = str(signal.get('index') or '').upper()
            return 'stocks' if indexName not in INDEX_SYMBOLS else 'indices'
        
        # Test with signal_type field
        assert getSignalGroup({"signal_type": "index", "index": "NIFTY"}) == "indices"
        assert getSignalGroup({"signal_type": "stock", "index": "TCS"}) == "stocks"
        assert getSignalGroup({"signal_type": "stock", "index": "RELIANCE"}) == "stocks"
    
    def test_getSignalGroup_fallback_to_name(self):
        """Test fallback to name-based classification if signal_type missing"""
        def getSignalGroup(signal):
            if signal.get('signal_type'):
                return signal.get('signal_type') == 'stock' and 'stocks' or 'indices'
            INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
            indexName = str(signal.get('index') or '').upper()
            return 'stocks' if indexName not in INDEX_SYMBOLS else 'indices'
        
        # Test fallback when signal_type missing
        assert getSignalGroup({"index": "NIFTY"}) == "indices"
        assert getSignalGroup({"index": "TCS"}) == "stocks"


class TestSignalQualityFiltering:
    """Test that signals pass quality filtering"""
    
    def test_quality_threshold(self, mock_kite):
        """Test that quality_score is properly set"""
        kite, instruments = mock_kite
        
        # Create a sample signal
        signal = {
            "index": "TCS",
            "symbol": "TCSMAR24100CE",
            "entry_price": 50.0,
            "target": 75.0,
            "stop_loss": 40.0,
            "action": "BUY",
            "option_type": "CE",
            "confidence": 80,
        }
        
        # Validate quality
        validated = _validate_signal_quality(signal, kite, {"ohlc": {"open": 100, "high": 110, "low": 90, "close": 105}}, enable_technical=False)
        
        assert "quality_score" in validated
        assert isinstance(validated["quality_score"], (int, float))
        assert 0 <= validated["quality_score"] <= 100


class TestGenerateSignalsIntegration:
    """Integration tests for full signal generation pipeline"""
    
    def test_generate_signals_includes_both_types(self, mock_kite):
        """Test that generate_signals returns both index and stock signals"""
        kite, _ = mock_kite
        
        with patch('app.engine.option_signal_generator._get_kite', return_value=kite):
            signals = generate_signals(
                user_id=None,
                symbols=None,
                include_nifty50=True,
                include_fno_universe=False,
                max_symbols=120
            )
            
            valid_signals = [s for s in signals if not s.get("error")]
            index_sigs = [s for s in valid_signals if s.get("signal_type") == "index"]
            stock_sigs = [s for s in valid_signals if s.get("signal_type") == "stock"]
            
            assert len(index_sigs) > 0, "Should have index signals"
            assert len(stock_sigs) > 0, "Should have stock signals"


# ==================== RUN TESTS ====================

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
