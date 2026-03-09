#!/usr/bin/env python3
"""
Test endpoint to check real signal generation with credentials.
This simulates what the frontend sees.
"""
import sys
sys.path.insert(0, 'f:\\ALGO\\backend')

from app.engine.option_signal_generator import generate_signals_advanced
import asyncio
import json

async def test_signals():
    print("[TEST] Generating signals WITH include_nifty50=True\n")
    
    # This matches what the frontend calls
    signals = await generate_signals_advanced(
        user_id=None,
        mode="balanced",
        symbols=None,
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=120,
    )
    
    print(f"Total signals returned: {len(signals)}\n")
    
    # Categorize
    index_signals = []
    stock_signals = []
    error_signals = []
    
    for sig in signals:
        if sig.get("error"):
            error_signals.append(sig)
        elif sig.get("signal_type") == "stock":
            stock_signals.append(sig)
        elif sig.get("signal_type") == "index":
            index_signals.append(sig)
        else:
            # Fallback: check index field
            idx = sig.get("index", "")
            if idx in ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY"]:
                index_signals.append(sig)
            else:
                stock_signals.append(sig)
    
    print(f"Results:")
    print(f"  Index signals: {len(index_signals)}")
    print(f"  Stock signals: {len(stock_signals)}")
    print(f"  Error signals: {len(error_signals)}")
    print()
    
    # Show details
    if index_signals:
        print("INDEX SIGNALS:")
        for sig in index_signals[:3]:
            print(f"  - {sig.get('index')}: {sig.get('symbol', 'N/A')} (Q: {sig.get('quality_score', 'N/A')})")
    
    if stock_signals:
        print("\nSTOCK SIGNALS:")
        for sig in stock_signals[:5]:
            print(f"  - {sig.get('index')}: {sig.get('symbol', 'N/A')} (Q: {sig.get('quality_score', 'N/A')})")
    
    if error_signals:
        print(f"\nERROR SIGNALS ({len(error_signals)} total):")
        for sig in error_signals[:3]:
            print(f"  - {sig.get('index')}: {sig.get('error', 'Unknown error')}")

asyncio.run(test_signals())
