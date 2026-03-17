#!/usr/bin/env python3
"""
Comprehensive test to trace the entire signal pipeline
showing exactly what backend returns and how it should be classified
"""
import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

from app.engine.option_signal_generator import (
    _build_scan_symbol_universe,
    generate_signals,
    generate_signals_advanced,
    NIFTY_50_SYMBOLS
)
import asyncio

print("=" * 100)
print("[COMPREHENSIVE DEBUG] Full Signal Pipeline Analysis")
print("=" * 100)

def analyze_signal_structure(signal):
    """Analyze a signal's structure and classification logic"""
    return {
        "has_error": bool(signal.get("error")),
        "index": signal.get("index"),
        "symbol": signal.get("symbol"),
        "signal_type": signal.get("signal_type"),
        "quality": signal.get("quality_score"),
        "confidence": signal.get("confirmation_score") or signal.get("confidence"),
        "option_type": signal.get("option_type"),
    }

async def test_full_pipeline():
    """Test the complete signal generation and classification pipeline"""
    
    print("\n[STEP 1] Test generate_signals with include_nifty50=True")
    print("-" * 100)
    
    signals = generate_signals(
        user_id=None,
        symbols=None,
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=120
    )
    
    print(f"Total signals returned: {len(signals)}")
    
    # Analyze by error status
    error_signals = [s for s in signals if s.get("error")]
    valid_signals = [s for s in signals if not s.get("error")]
    
    print(f"  - Valid signals: {len(valid_signals)}")
    print(f"  - Error signals: {len(error_signals)}")
    
    if error_signals:
        print(f"\nError signals sample:")
        for sig in error_signals[:3]:
            print(f"  - {sig.get('index')}: {sig.get('error')}")
    
    # Analyze valid signals by signal_type
    print(f"\nValid signals breakdown:")
    index_signals = [s for s in valid_signals if s.get("signal_type") == "index"]
    stock_signals = [s for s in valid_signals if s.get("signal_type") == "stock"]
    unknown_signals = [s for s in valid_signals if s.get("signal_type") is None]
    
    print(f"  - Index signals (signal_type='index'): {len(index_signals)}")
    print(f"  - Stock signals (signal_type='stock'): {len(stock_signals)}")
    print(f"  - Unknown signals (signal_type=null): {len(unknown_signals)}")
    
    print(f"\nSample signal structures:")
    for i, sig in enumerate(valid_signals[:3]):
        analysis = analyze_signal_structure(sig)
        print(f"\n  Signal {i+1}:")
        for key, val in analysis.items():
            print(f"    {key}: {val}")
    
    # Step 2: Test with generate_signals_advanced
    print("\n" + "=" * 100)
    print("[STEP 2] Test generate_signals_advanced (what frontend calls)")
    print("-" * 100)
    
    advanced_signals = await generate_signals_advanced(
        user_id=None,
        mode="balanced",
        symbols=None,
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=120,
    )
    
    print(f"Total signals from generate_signals_advanced: {len(advanced_signals)}")
    
    # Check what fields are present
    if advanced_signals:
        sample_sig = advanced_signals[0]
        print(f"\nSample signal fields:")
        for key in sorted(sample_sig.keys()):
            value = sample_sig[key]
            if isinstance(value, (dict, list)) and len(str(value)) > 50:
                print(f"  {key}: {type(value).__name__} (length: {len(value)})")
            else:
                print(f"  {key}: {value}")
    
    # Step 3: Simulate frontend classification
    print("\n" + "=" * 100)
    print("[STEP 3] Frontend Classification Logic")
    print("-" * 100)
    
    def frontend_getSignalGroup(signal):
        """Simulate frontend getSignalGroup function"""
        INDEX_SYMBOLS = {'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'}
        
        # NEW: Check signal_type field from backend (preferred)
        if signal.get('signal_type'):
            return signal.get('signal_type') == 'stock' and 'stocks' or 'indices'
        
        # FALLBACK: Old logic based on index name
        indexName = str(signal.get('index') or '').upper()
        if indexName in INDEX_SYMBOLS:
            return 'indices'
        
        # Check if symbol contains index name
        symbol = str(signal.get('symbol') or '').upper()
        for idx in INDEX_SYMBOLS:
            if idx in symbol:
                return 'indices'
        
        return 'stocks'
    
    # Classify all valid signals
    classified = {}
    for sig in valid_signals:
        group = frontend_getSignalGroup(sig)
        if group not in classified:
            classified[group] = []
        classified[group].append(sig)
    
    print(f"Frontend classification results:")
    for group, sigs in classified.items():
        print(f"  - {group}: {len(sigs)}")
        if sigs:
            print(f"    Sample: {sigs[0].get('index')} / {sigs[0].get('symbol')}")
    
    # Step 4: Check quality filtering
    print("\n" + "=" * 100)
    print("[STEP 4] Quality Filtering (as done in scanMarketForQualityTrades)")
    print("-" * 100)
    
    MIN_QUALITY = 70
    filtered = [s for s in valid_signals if s.get('quality_score', 0) >= MIN_QUALITY]
    
    print(f"Signals with quality >= {MIN_QUALITY}%: {len(filtered)}")
    
    filtered_by_group = {}
    for sig in filtered:
        group = frontend_getSignalGroup(sig)
        if group not in filtered_by_group:
            filtered_by_group[group] = []
        filtered_by_group[group].append(sig)
    
    print(f"\nFiltered by group:")
    for group, sigs in filtered_by_group.items():
        print(f"  - {group}: {len(sigs)}")
    
    # Step 5: Check missing symbols in stock universe
    print("\n" + "=" * 100)
    print("[STEP 5] Stock Universe Analysis")
    print("-" * 100)
    
    universe = _build_scan_symbol_universe(
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=120,
        instruments_nfo=[]
    )
    
    print(f"Symbol universe with include_nifty50=True:")
    print(f"  Total symbols: {len(universe)}")
    print(f"  Indices (4): {universe[:4]}")
    print(f"  Sample stocks: {universe[4:10]}")
    
    # Check if we should be getting stock signals
    stocks_in_universe = [s for s in universe if s not in ['NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY']]
    print(f"  Stock symbols in universe: {len(stocks_in_universe)}")
    
    # See which stocks from requests were processed
    stocks_returned = [s.get('index') for s in valid_signals 
                      if s.get('index') not in ['NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY']]
    print(f"  Stock signals returned: {len(stocks_returned)}")
    if stocks_returned:
        print(f"    Stocks: {stocks_returned}")

asyncio.run(test_full_pipeline())

print("\n" + "=" * 100)
print("[SUMMARY]")
print("=" * 100)
print("""
If you see:
  All (5) Indices (5) Stocks (0)

This means:
1. Backend is NOT returning any stock signals (only index error or success)
2. This happens when credentials missing OR symbol universe not built
3. Frontend getSignalGroup() is working, but has no stock signals to classify

Next steps:
1. Check if generate_signals ACTUALLY builds symbol universe with include_nifty50
2. Verify _get_kite() is returning valid credentials
3. Check if fetch_index_option_chain() is being called for stocks
4. See if stock options exist in your Zerodha account
""")
