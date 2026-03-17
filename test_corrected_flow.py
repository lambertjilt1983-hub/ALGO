#!/usr/bin/env python3
"""
Test that simulates having valid Zerodha credentials with CORRECT FUTURE EXPIRIES
"""
import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

from unittest.mock import Mock, patch
from datetime import datetime, timedelta, date
from app.engine.option_signal_generator import (
    generate_signals,
    _build_scan_symbol_universe,
    fetch_index_option_chain,
    NIFTY_50_SYMBOLS
)

print("=" * 100)
print("[DETAILED ANALYSIS] Signal Generation Flow with CORRECTED Test Data")
print("=" * 100)

# Get future expiry date
today = date.today()
future_expiry = today + timedelta(days=10)  # 10 days in future

print(f"\nToday: {today}")
print(f"Using expiry: {future_expiry}")

# Create mock Kite object
mock_kite = Mock()

# Mock instruments - return sample NFO data with FUTURE expiry dates
mock_nfo_instruments = [
    # Index options - NIFTY
    {"tradingsymbol": "NIFTY23OCT25000CE", "segment": "NFO-OPT", "name": "NIFTY", "expiry": future_expiry, "strike": 25000, "instrument_type": "CE", "lot_size": 50},
    {"tradingsymbol": "NIFTY23OCT25000PE", "segment": "NFO-OPT", "name": "NIFTY", "expiry": future_expiry, "strike": 25000, "instrument_type": "PE", "lot_size": 50},
    
    # Index options - BANKNIFTY
    {"tradingsymbol": "BANKNIFTY23OCT55000CE", "segment": "NFO-OPT", "name": "BANKNIFTY", "expiry": future_expiry, "strike": 55000, "instrument_type": "CE", "lot_size": 30},
    {"tradingsymbol": "BANKNIFTY23OCT55000PE", "segment": "NFO-OPT", "name": "BANKNIFTY", "expiry": future_expiry, "strike": 55000, "instrument_type": "PE", "lot_size": 30},
    
    # Stock options - TCS
    {"tradingsymbol": "TCSMAR24100CE", "segment": "NFO-OPT", "name": "TCS", "expiry": future_expiry, "strike": 4100, "instrument_type": "CE", "lot_size": 1},
    {"tradingsymbol": "TCSMAR24100PE", "segment": "NFO-OPT", "name": "TCS", "expiry": future_expiry, "strike": 4100, "instrument_type": "PE", "lot_size": 1},
    
    # Stock options - INFY
    {"tradingsymbol": "INFYMAR24800CE", "segment": "NFO-OPT", "name": "INFY", "expiry": future_expiry, "strike": 800, "instrument_type": "CE", "lot_size": 1},
    {"tradingsymbol": "INFYMAR24800PE", "segment": "NFO-OPT", "name": "INFY", "expiry": future_expiry, "strike": 800, "instrument_type": "PE", "lot_size": 1},
    
    # Stock options - RELIANCE
    {"tradingsymbol": "RELIANCEMAR243000CE", "segment": "NFO-OPT", "name": "RELIANCE", "expiry": future_expiry, "strike": 3000, "instrument_type": "CE", "lot_size": 1},
    {"tradingsymbol": "RELIANCEMAR243000PE", "segment": "NFO-OPT", "name": "RELIANCE", "expiry": future_expiry, "strike": 3000, "instrument_type": "PE", "lot_size": 1},
]

mock_kite.instruments = Mock(return_value=mock_nfo_instruments)

# Mock quote - return sample price data
def mock_quote(symbols):
    quotes = {
        "NSE:NIFTY 50": {
            "last_price": 25000, 
            "open_price": 24900, 
            "ohlc": {"open": 24900, "high": 25100, "low": 24800, "close": 25000},
            "volume": 1000000
        },
        "NSE:TCS": {
            "last_price": 4100, 
            "open_price": 4050, 
            "ohlc": {"open": 4050, "high": 4150, "low": 4000, "close": 4100},
            "volume": 500000
        },
        "NSE:INFY": {
            "last_price": 800, 
            "open_price": 790, 
            "ohlc": {"open": 790, "high": 820, "low": 780, "close": 800},
            "volume": 2000000
        },
        "NSE:RELIANCE": {
            "last_price": 3000,
            "open_price": 2950,
            "ohlc": {"open": 2950, "high": 3050, "low": 2900, "close": 3000},
            "volume": 1500000
        },
        "NSE:BANKNIFTY": {
            "last_price": 55000,
            "open_price": 54900,
            "ohlc": {"open": 54900, "high": 55100, "low": 54800, "close": 55000},
            "volume": 800000
        },
        "NFO:NIFTY23OCT25000CE": {"last_price": 150.5, "volume": 100000},
        "NFO:NIFTY23OCT25000PE": {"last_price": 150.5, "volume": 100000},
        "NFO:BANKNIFTY23OCT55000CE": {"last_price": 500.0, "volume": 50000},
        "NFO:BANKNIFTY23OCT55000PE": {"last_price": 500.0, "volume": 50000},
        "NFO:TCSMAR24100CE": {"last_price": 25.0, "volume": 10000},
        "NFO:TCSMAR24100PE": {"last_price": 25.0, "volume": 10000},
        "NFO:INFYMAR24800CE": {"last_price": 30.0, "volume": 20000},
        "NFO:INFYMAR24800PE": {"last_price": 30.0, "volume": 20000},
        "NFO:RELIANCEMAR243000CE": {"last_price": 100.0, "volume": 15000},
        "NFO:RELIANCEMAR243000PE": {"last_price": 100.0, "volume": 15000},
    }
    return {sym: quotes.get(sym, {"last_price": 100, "ohlc": {"open": 100}}) for sym in symbols}

mock_kite.quote = mock_quote

print("\n[TEST] Simulate generate_signals with CORRECTED mock")
print("-" * 100)

# Patch the _get_kite function to return our mock
with patch('app.engine.option_signal_generator._get_kite', return_value=mock_kite):
    signals = generate_signals(
        user_id=None,
        symbols=None,
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=120
    )
    
    print(f"\nTotal signals generated: {len(signals)}")
    
    # Analyze signals
    valid_signals = [s for s in signals if not s.get("error")]
    error_signals = [s for s in signals if s.get("error")]
    
    print(f"  Valid signals: {len(valid_signals)}")
    print(f"  Error signals: {len(error_signals)}")
    
    # Breakdown by signal_type
    index_sigs = [s for s in valid_signals if s.get("signal_type") == "index"]
    stock_sigs = [s for s in valid_signals if s.get("signal_type") == "stock"]
    unknown_type = [s for s in valid_signals if s.get("signal_type") is None]
    
    print(f"\nValid signals breakdown:")
    print(f"  Index signals (signal_type='index'): {len(index_sigs)}")
    print(f"  Stock signals (signal_type='stock'): {len(stock_sigs)}")
    print(f"  Unknown type (signal_type=None): {len(unknown_type)}")
    
    # Show samples
    if index_sigs:
        print(f"\nIndex signals (sample {min(3, len(index_sigs))}):")
        for sig in index_sigs[:3]:
            print(f"  - {sig.get('index')}: {sig.get('symbol')} | Q:{sig.get('quality_score')} C:{sig.get('confirmation_score')}")
    
    if stock_sigs:
        print(f"\nStock signals (sample {min(3, len(stock_sigs))}):")
        for sig in stock_sigs[:3]:
            print(f"  - {sig.get('index')}: {sig.get('symbol')} | Q:{sig.get('quality_score')} C:{sig.get('confirmation_score')}")
    
    # Show errors
    if error_signals:
        print(f"\nError signals (showing first 3):")
        for sig in error_signals[:3]:
            print(f"  - {sig.get('index')}: {sig.get('error')}")
        
        # Error breakdown
        index_errors = [s for s in error_signals if s.get('index') in ['NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY']]
        stock_errors = [s for s in error_signals if s.get('index') not in ['NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY']]
        print(f"\n  Index errors: {len(index_errors)}")
        print(f"  Stock errors: {len(stock_errors)}")
        if stock_errors:
            print(f"  Stocks with errors: {[s.get('index') for s in stock_errors[:5]]}")

print("\n" + "=" * 100)
print("[SUMMARY]")
print("=" * 100)
print("""
Key findings:
1. If backend generates BOTH index and stock signals ✓ code is correct
2. If backend only generates SOME stocks as errors ✓ shows selective issue  
3. If no stocks appear at all ✗ symbol universe or fetching broken

The getSignalGroup() fix will work IF backend returns signal_type field.
Current issue: Backend might be putting errors into results for stocks.
""")
