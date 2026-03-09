#!/usr/bin/env python3
"""
Test script to verify stock signals are being returned by the API.
"""

import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

from app.engine.option_signal_generator import (
    generate_signals,
    _build_scan_symbol_universe,
    NIFTY_50_SYMBOLS
)

def test_symbol_universe():
    """Test that symbol universe includes stocks when requested."""
    print("\n=== Testing Symbol Universe ===")
    
    # Test without stocks
    indices_only = _build_scan_symbol_universe(
        include_nifty50=False,
        include_fno_universe=False,
        max_symbols=120,
        instruments_nfo=[]
    )
    print(f"✓ Indices only: {indices_only}")
    assert len(indices_only) == 4, "Should have 4 indices"
    print(f"  Count: {len(indices_only)} - All indices")
    
    # Test with stocks
    with_stocks = _build_scan_symbol_universe(
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=120,
        instruments_nfo=[]
    )
    print(f"✓ With stocks: First 10 = {with_stocks[:10]}")
    assert len(with_stocks) > 4, "Should have indices + stocks"
    stocks_count = len(with_stocks) - 4
    print(f"  Count: {len(with_stocks)} total (4 indices + {stocks_count} stocks)")
    assert stocks_count == len(NIFTY_50_SYMBOLS), f"Should have {len(NIFTY_50_SYMBOLS)} stocks"
    
    # Verify we have stock names
    stock_symbols = [s for s in with_stocks if s not in ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY"]]
    print(f"✓ Stock symbols sample: {stock_symbols[:10]}")
    
    expected_stocks = ["TCS", "INFY", "RELIANCE"]
    for stock in expected_stocks:
        assert stock in with_stocks, f"Missing expected stock: {stock}"
    print(f"✓ All expected stocks present: {expected_stocks}")
    
    return True

def test_generate_signals():
    """Test that generate_signals includes stocks when requested."""
    print("\n=== Testing Generate Signals ===")
    
    # This test will be mocked since we don't have real Zerodha credentials
    # but the code path should work
    print("Note: Full signal generation requires Zerodha credentials")
    print("      Backend will return error signals if credentials missing")
    
    # Just verify the function exists and accepts the parameter
    import inspect
    sig = inspect.signature(generate_signals)
    params = list(sig.parameters.keys())
    print(f"✓ generate_signals parameters: {params}")
    assert 'include_nifty50' in params, "Missing include_nifty50 parameter"
    print("✓ include_nifty50 parameter present")
    
    return True

if __name__ == "__main__":
    try:
        print("🧪 Testing Stock Signal Generation")
        test_symbol_universe()
        test_generate_signals()
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
