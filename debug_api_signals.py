#!/usr/bin/env python3
"""
Debug script to check what the API is actually returning
"""
import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

from app.engine.option_signal_generator import generate_signals

# Try to generate signals without credentials (will show what happens)
print("[DEBUG] Testing signal generation WITHOUT credentials...\n")

# Test 1: Indices only (default)
print("=" * 80)
print("[TEST 1] Indices Only (include_nifty50=False)")
print("=" * 80)
signals = generate_signals(
    user_id=None,
    symbols=None,
    include_nifty50=False,
    include_fno_universe=False,
    max_symbols=120
)
print(f"Returned {len(signals)} signals\n")
for sig in signals[:5]:  # Show first 5
    print(f"Symbol: {sig.get('index', 'N/A')}")
    print(f"  Error: {sig.get('error', 'N/A')}")
    print(f"  signal_type: {sig.get('signal_type', 'N/A')}")
    print()

# Test 2: With NIFTY 50
print("=" * 80)
print("[TEST 2] With NIFTY 50 Stocks (include_nifty50=True)")
print("=" * 80)
signals = generate_signals(
    user_id=None,
    symbols=None,
    include_nifty50=True,
    include_fno_universe=False,
    max_symbols=120
)
print(f"Returned {len(signals)} signals\n")

# Count by type
indices_signals = [s for s in signals if s.get('signal_type') == 'index']
stock_signals = [s for s in signals if s.get('signal_type') == 'stock']
error_signals = [s for s in signals if s.get('error')]

print(f"Summary:")
print(f"  Indices: {len(indices_signals)}")
print(f"  Stocks: {len(stock_signals)}")
print(f"  Errors: {len(error_signals)}")
print()

print("First 10 signals:")
for i, sig in enumerate(signals[:10]):
    print(f"{i+1}. Index: {sig.get('index', 'N/A')}, Type: {sig.get('signal_type', 'N/A')}, Error: {'Yes' if sig.get('error') else 'No'}")

if stock_signals:
    print("\n[OK] Stock signals ARE being generated!")
    print("Sample stock signals:")
    for sig in stock_signals[:3]:
        print(f"  - {sig.get('index')}: {sig.get('action')} (Quality: {sig.get('quality_score', 'N/A')})")
else:
    print("\n[ERROR] NO stock signals generated")
    print("   All returned signals have errors (missing Zerodha credentials)")
