#!/usr/bin/env python3
"""
Test that simulates having valid Zerodha credentials to see the full flow
"""
import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

from unittest.mock import Mock, patch
from app.engine.option_signal_generator import (
    generate_signals,
    _build_scan_symbol_universe,
    fetch_index_option_chain,
    NIFTY_50_SYMBOLS
)

print("=" * 100)
print("[DETAILED ANALYSIS] Signal Generation Flow with Mocked Credentials")
print("=" * 100)

# Create mock Kite object
mock_kite = Mock()

# Mock instruments - return sample NFO data
mock_nfo_instruments = [
    # Index options
    {"tradingsymbol": "NIFTY23OCT25000CE", "segment": "NFO-OPT", "name": "NIFTY", "expiry": "2024-10-25", "strike": 25000, "instrument_type": "CE", "lot_size": 50},
    {"tradingsymbol": "NIFTY23OCT25000PE", "segment": "NFO-OPT", "name": "NIFTY", "expiry": "2024-10-25", "strike": 25000, "instrument_type": "PE", "lot_size": 50},
    
    # Stock options - TCS
    {"tradingsymbol": "TCSMAR24100CE", "segment": "NFO-OPT", "name": "TCS", "expiry": "2024-03-28", "strike": 4100, "instrument_type": "CE", "lot_size": 1},
    {"tradingsymbol": "TCSMAR24100PE", "segment": "NFO-OPT", "name": "TCS", "expiry": "2024-03-28", "strike": 4100, "instrument_type": "PE", "lot_size": 1},
    
    # Stock options - INFY
    {"tradingsymbol": "INFYMAR24800CE", "segment": "NFO-OPT", "name": "INFY", "expiry": "2024-03-28", "strike": 800, "instrument_type": "CE", "lot_size": 1},
    {"tradingsymbol": "INFYMAR24800PE", "segment": "NFO-OPT", "name": "INFY", "expiry": "2024-03-28", "strike": 800, "instrument_type": "PE", "lot_size": 1},
]

mock_kite.instruments = Mock(return_value=mock_nfo_instruments)

# Mock quote - return sample price data
def mock_quote(symbols):
    quotes = {
        "NSE:NIFTY 50": {"last_price": 25000, "open_price": 24900, "high": 25100, "low": 24800, "close": 25000, "volume": 1000000},
        "NSE:TCS": {"last_price": 4100, "open_price": 4050, "high": 4150, "low": 4000, "close": 4100, "volume": 500000},
        "NSE:INFY": {"last_price": 800, "open_price": 790, "high": 820, "low": 780, "close": 800, "volume": 2000000},
        "NFO:NIFTY23OCT25000CE": {"last_price": 150.5, "volume": 100000},
        "NFO:NIFTY23OCT25000PE": {"last_price": 150.5, "volume": 100000},
        "NFO:TCSMAR24100CE": {"last_price": 25.0, "volume": 10000},
        "NFO:TCSMAR24100PE": {"last_price": 25.0, "volume": 10000},
        "NFO:INFYMAR24800CE": {"last_price": 30.0, "volume": 20000},
        "NFO:INFYMAR24800PE": {"last_price": 30.0, "volume": 20000},
    }
    return {sym: quotes.get(sym, {"last_price": 100}) for sym in symbols}

mock_kite.quote = mock_quote

print("\n[TEST 1] Check symbol universe building")
print("-" * 100)

universe = _build_scan_symbol_universe(
    include_nifty50=True,
    include_fno_universe=False,
    max_symbols=120,
    instruments_nfo=mock_nfo_instruments
)

print(f"Symbol universe: {len(universe)} total")
print(f"  Indices: {[s for s in universe if s in ['NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY']]}")
print(f"  Stocks: {[s for s in universe if s not in ['NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY']]}")

print("\n[TEST 2] Check which instruments match expected symbols")
print("-" * 100)

# Check NIFTY
nifty_matches = [i for i in mock_nfo_instruments if i["name"] == "NIFTY" and i["segment"] == "NFO-OPT"]
print(f"NIFTY instruments found: {len(nifty_matches)}")

# Check TCS (should match by tradingsymbol starting with TCS)
tcs_matches = [i for i in mock_nfo_instruments if i["tradingsymbol"].startswith("TCS") and i["segment"] == "NFO-OPT"]
print(f"TCS instruments found (startswith 'TCS'): {len(tcs_matches)}")

# Check INFY (should match by tradingsymbol starting with INFY)
infy_matches = [i for i in mock_nfo_instruments if i["tradingsymbol"].startswith("INFY") and i["segment"] == "NFO-OPT"]
print(f"INFY instruments found (startswith 'INFY'): {len(infy_matches)}")

print("\n[TEST 3] Test fetch_index_option_chain for NIFTY")
print("-" * 100)

try:
    nifty_result = fetch_index_option_chain(
        index_name="NIFTY",
        kite=mock_kite,
        instruments_nfo=mock_nfo_instruments,
    )
    
    if isinstance(nifty_result, list):
        print(f"NIFTY returned {len(nifty_result)} signals:")
        for sig in nifty_result:
            print(f"  - {sig.get('symbol')}: {sig.get('action')} (signal_type: {sig.get('signal_type', 'MISSING')})")
    else:
        print(f"NIFTY returned error: {nifty_result.get('error', 'Unknown')}")
except Exception as e:
    print(f"Error fetching NIFTY: {e}")

print("\n[TEST 4] Test fetch_index_option_chain for TCS (stock)")
print("-" * 100)

try:
    tcs_result = fetch_index_option_chain(
        index_name="TCS",
        kite=mock_kite,
        instruments_nfo=mock_nfo_instruments,
    )
    
    if isinstance(tcs_result, list):
        print(f"TCS returned {len(tcs_result)} signals:")
        for sig in tcs_result:
            print(f"  - {sig.get('symbol')}: {sig.get('action')} (signal_type: {sig.get('signal_type', 'MISSING')})")
    else:
        error = tcs_result.get('error', 'Unknown')
        print(f"TCS returned error: {error}")
        print(f"\nDebug info from error: {tcs_result.get('debug', {})}")
except Exception as e:
    print(f"Error fetching TCS: {e}")
    import traceback
    traceback.print_exc()

print("\n[TEST 5] Simulate generate_signals with perfect mock")
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
    
    print(f"Total signals generated: {len(signals)}")
    
    # Analyze signals
    valid_signals = [s for s in signals if not s.get("error")]
    error_signals = [s for s in signals if s.get("error")]
    
    print(f"  Valid signals: {len(valid_signals)}")
    print(f"  Error signals: {len(error_signals)}")
    
    if valid_signals:
        print(f"\nValid signals by type:")
        index_sigs = [s for s in valid_signals if s.get("signal_type") == "index"]
        stock_sigs = [s for s in valid_signals if s.get("signal_type") == "stock"]
        print(f"  Indices: {len(index_sigs)}")
        print(f"  Stocks: {len(stock_sigs)}")
        
        if index_sigs:
            print(f"\n  Index signal sample:")
            sig = index_sigs[0]
            print(f"    {sig.get('index')}: {sig.get('symbol')} (signal_type: {sig.get('signal_type')})")
        
        if stock_sigs:
            print(f"\n  Stock signal sample:")
            sig = stock_sigs[0]
            print(f"    {sig.get('index')}: {sig.get('symbol')} (signal_type: {sig.get('signal_type')})")

print("\n" + "=" * 100)
print("[ANALYSIS]")
print("=" * 100)
print("""
Results interpretation:
- If NIFTY generates signals with signal_type='index' ✓
- If TCS generates signals with signal_type='stock' ✓
  Then backend code is CORRECT
  
- If TCS returns error (No option chain data for stock TCS)
  Then stock options don't exist in mock instruments
  
- If TEST 5 shows valid signals for NIFTY but not TCS
  Then the backend is working but something filters out stocks
""")
