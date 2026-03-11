#!/usr/bin/env python3
"""
Simple test to check what signals are returned from the API
"""
import sys
import os
sys.path.insert(0, 'f:/ALGO/backend')
os.environ['ENVIRONMENT'] = 'production'

# Set up environment
from pathlib import Path
from dotenv import load_dotenv
env_file = Path('f:/ALGO/backend/.env')
if env_file.exists():
    load_dotenv(env_file)

from app.engine.option_signal_generator import (
    _build_scan_symbol_universe,
    NIFTY_50_SYMBOLS
)

print("=" * 80)
print("STOCK SYMBOL UNIVERSE TEST")
print("=" * 80)

# Test 1: Check NIFTY_50_SYMBOLS
print(f"\n✅ NIFTY_50_SYMBOLS count: {len(NIFTY_50_SYMBOLS)}")
print(f"   Sample: {list(NIFTY_50_SYMBOLS)[:5]}")

# Test 2: Build universe with include_nifty50=True
print("\n✅ Building symbol universe with include_nifty50=True:")
universe = _build_scan_symbol_universe(
    include_nifty50=True,
    include_fno_universe=False,
    max_symbols=60,
    instruments_nfo=[]
)

indices = ['BANKNIFTY', 'NIFTY', 'SENSEX', 'FINNIFTY']
index_symbols = [s for s in universe if s in indices]
stock_symbols = [s for s in universe if s not in indices]

print(f"   Total symbols: {len(universe)}")
print(f"   Indices: {index_symbols} ({len(index_symbols)})")
print(f"   Stocks: {stock_symbols[:10]}... ({len(stock_symbols)} total)")

# Test 3: Verify all expected fields
print("\n✅ Verification:")
print(f"   - All 4 indices included: {all(s in universe for s in indices)}")
print(f"   - Stocks included: {len(stock_symbols) > 0}")
print(f"   - NIFTY 50 coverage: {len([s for s in stock_symbols if s in NIFTY_50_SYMBOLS])}/{len(NIFTY_50_SYMBOLS)}")

print("\n" + "=" * 80)
