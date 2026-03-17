#!/usr/bin/env python3
"""
Diagnostic script to test stock signal generation
"""
import sys
sys.path.insert(0, 'f:/ALGO/backend')

from app.engine.option_signal_generator import (
    generate_signals,
    _build_scan_symbol_universe,
    NIFTY_50_SYMBOLS
)

print("=" * 80)
print("STOCK SIGNAL GENERATION DIAGNOSTIC")
print("=" * 80)

# Test 1: Check if NIFTY_50_SYMBOLS is populated
print("\n✅ Test 1: NIFTY_50_SYMBOLS loaded")
print(f"   Count: {len(NIFTY_50_SYMBOLS)}")
print(f"   Sample stocks: {list(NIFTY_50_SYMBOLS)[:5]}")

# Test 2: Test symbol universe with stocks disabled
print("\n✅ Test 2: Symbol universe WITHOUT stocks")
universe_indices_only = _build_scan_symbol_universe(
    include_nifty50=False,
    include_fno_universe=False, 
    max_symbols=60,
    instruments_nfo=[]
)
print(f"   Symbols: {universe_indices_only}")
print(f"   Count: {len(universe_indices_only)}")

# Test 3: Test symbol universe with stocks enabled
print("\n✅ Test 3: Symbol universe WITH NIFTY50 stocks")
universe_with_stocks = _build_scan_symbol_universe(
    include_nifty50=True,
    include_fno_universe=False,
    max_symbols=60,
    instruments_nfo=[]
)
print(f"   Total count: {len(universe_with_stocks)}")
print(f"   Indices: {[s for s in universe_with_stocks if s in ['BANKNIFTY', 'NIFTY', 'SENSEX', 'FINNIFTY']]}")
indices = ['BANKNIFTY', 'NIFTY', 'SENSEX', 'FINNIFTY']
stocks = [s for s in universe_with_stocks if s not in indices]
print(f"   Stocks: {stocks[:10]}...")  # Show first 10 stocks
print(f"   Stock count: {len(stocks)}")

# Test 4: Generate signals without stocks
print("\n✅ Test 4: Generate signals WITHOUT stocks")
try:
    signals_indices_only = generate_signals(
        symbols=None,
        include_nifty50=False,
        include_fno_universe=False,
        max_symbols=60
    )
    print(f"   Signals generated: {len(signals_indices_only)}")
    for sig in signals_indices_only[:3]:
        print(f"      - {sig.get('index')}: signal_type={sig.get('signal_type')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 5: Generate signals with stocks
print("\n✅ Test 5: Generate signals WITH stocks (include_nifty50=True)")
try:
    signals_with_stocks = generate_signals(
        symbols=None,
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=60
    )
    print(f"   Signals generated: {len(signals_with_stocks)}")
    
    # Categorize signals
    index_signals = [s for s in signals_with_stocks if s.get('signal_type') == 'index']
    stock_signals = [s for s in signals_with_stocks if s.get('signal_type') == 'stock']
    error_signals = [s for s in signals_with_stocks if s.get('error')]
    no_type_signals = [s for s in signals_with_stocks if 'signal_type' not in s]
    
    print(f"   Index signals: {len(index_signals)}")
    print(f"   Stock signals: {len(stock_signals)}")
    print(f"   Error signals: {len(error_signals)}")
    print(f"   Signals without signal_type field: {len(no_type_signals)}")
    
    if stock_signals:
        print(f"\n   📊 Sample stock signals:")
        for sig in stock_signals[:3]:
            print(f"      - Symbol: {sig.get('symbol')}, Index: {sig.get('index')}, Type: {sig.get('signal_type')}")
    else:
        print(f"\n   ⚠️  NO STOCK SIGNALS GENERATED!")
        if error_signals:
            print(f"\n   📋 Error signals:")
            for sig in error_signals[:3]:
                print(f"      - {sig.get('index')}: {sig.get('error')}")
                
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
