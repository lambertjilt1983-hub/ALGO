#!/usr/bin/env python3
"""
Comprehensive test to understand why stock signals aren't showing
"""
import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

from app.engine.option_signal_generator import (
    _build_scan_symbol_universe,
    generate_signals,
    NIFTY_50_SYMBOLS
)

print("=" * 80)
print("[ANALYSIS] Stock Signals Issue Debug")
print("=" * 80)

# Step 1: Check symbol universe building
print("\n[STEP 1] Symbol Universe Building")
print("-" * 80)

universe_indices_only = _build_scan_symbol_universe(
    include_nifty50=False,
    include_fno_universe=False,
    max_symbols=120,
    instruments_nfo=[]
)

universe_with_stocks = _build_scan_symbol_universe(
    include_nifty50=True,
    include_fno_universe=False,
    max_symbols=120,
    instruments_nfo=[]
)

print(f"Indices only: {universe_indices_only}")
print(f"With stocks: {len(universe_with_stocks)} total")
print(f"  - Indices: 4 ({universe_with_stocks[:4]})")
print(f"  - Stocks: {len(universe_with_stocks) - 4} (starting with {universe_with_stocks[4:10]})")

# Step 2: Check that stocks are actually in NIFTY_50_SYMBOLS
print(f"\n[STEP 2] NIFTY 50 Symbol Validation")
print("-" * 80)
print(f"NIFTY_50_SYMBOLS count: {len(NIFTY_50_SYMBOLS)}")
print(f"Sample stocks: {NIFTY_50_SYMBOLS[:10]}")

expected_stocks = ["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK"]
for stock in expected_stocks:
    status = "FOUND" if stock in NIFTY_50_SYMBOLS else "MISSING"
    print(f"  {stock}: {status}")

# Step 3: Simulate what happens when generate_signals is called
print(f"\n[STEP 3] generate_signals() Call Simulation")
print("-" * 80)
print("When generate_signals() is called with include_nifty50=True:")
print("  1. Checks for Zerodha credentials")
print("  2. If missing: Returns 4 index error signals ONLY (BUG: No stocks built)")
print("  3. If present: Builds symbol universe with stocks")
print("  4. Calls fetch_index_option_chain() for EACH symbol")
print("  5. Returns all signals (indices + stocks)")

# Step 4: Check current issue
print(f"\n[STEP 4] Current Issue Analysis")
print("-" * 80)
print("User Output: All (1) Indices (1) Stocks (0)")
print("This means one of:")
print("  A) Credentials missing -> Only index errors returned (unlikely, they see 1 signal)")
print("  B) Stock option chains don't exist on NSE for selected stocks")
print("  C) Backend is returning stock error signals (not included in count)")
print("  D) Frontend getSignalGroup() classifying stocks as indices (LIKELY)")
print("  E) Auto-scan not running to call API with include_nifty50=true")

# Step 5: Frontend fix verification
print(f"\n[STEP 5] Frontend Fix Verification")
print("-" * 80)
print("Frontend getSignalGroup() function should:")
print("  1. Check signal.signal_type field (NEW)")
print("  2. If signal_type == 'stock': return 'stocks'")
print("  3. Fallback to name-based logic if signal_type missing")
print()

def test_classification(signal):
    """Test how signal would be classified by old vs new getSignalGroup"""
    INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
    
    # OLD WAY (before fix)
    indexName = str(signal.get('index') or '').upper()
    old_result = 'indices' if indexName in INDEX_SYMBOLS else 'stocks'
    
    # NEW WAY (after fix)
    if signal.get('signal_type'):
        new_result = 'stocks' if signal['signal_type'] == 'stock' else 'indices'
    else:
        new_result = 'indices' if indexName in INDEX_SYMBOLS else 'stocks'
    
    return old_result, new_result

test_signals = [
    {'index': 'NIFTY', 'symbol': 'NIFTY2631023800CE', 'signal_type': 'index'},
    {'index': 'TCS', 'symbol': 'TCSCE4800CE', 'signal_type': 'stock'},
    {'index': 'TCS', 'symbol': 'TCSCE4800CE'},  # Missing signal_type
]

print("Signal Classification Test:")
for sig in test_signals:
    old, new = test_classification(sig)
    match = "SAME" if old == new else "DIFFERENT"
    print(f"  {sig['symbol']}: OLD={old}, NEW={new} [{match}]")

print("\n[CONCLUSION]")
print("-" * 80)
print("To fix 'Stocks (0)' issue:")
print("  1. Ensure Zerodha credentials are configured (you have them)")
print("  2. Browser must reload to use updated getSignalGroup() function")
print("  3. Auto-scan must trigger to call API with include_nifty50=true")
print("  4. Backend must return stock signals (requires valid option chains)")
print("  5. Frontend must classify them using signal_type field")
