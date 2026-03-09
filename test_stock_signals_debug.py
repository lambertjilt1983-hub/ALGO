#!/usr/bin/env python3
"""
Debug script to check if stock signals are being generated and returned by the API endpoint.
"""
import sys
import asyncio
sys.path.insert(0, 'f:\\ALGO\\backend')

from app.engine.option_signal_generator import generate_signals, generate_signals_advanced

async def test_stock_signals():
    """Test that stock signals are actually being generated."""
    
    print("=" * 80)
    print("TEST 1: Generate signals WITH include_nifty50=True")
    print("=" * 80)
    
    signals = generate_signals(
        include_nifty50=True,
        include_fno_universe=False,
        max_symbols=60
    )
    
    print(f"\n📊 Total signals generated: {len(signals)}")
    
    # Separate index vs stock signals
    index_signals = [s for s in signals if not s.get('error') and s.get('signal_type') == 'index']
    stock_signals = [s for s in signals if not s.get('error') and s.get('signal_type') == 'stock']
    error_signals = [s for s in signals if s.get('error')]
    
    print(f"   - Index signals: {len(index_signals)}")
    print(f"   - Stock signals: {len(stock_signals)}")
    print(f"   - Error signals: {len(error_signals)}")
    
    if stock_signals:
        print(f"\n✅ STOCK SIGNALS FOUND! First 3:")
        for sig in stock_signals[:3]:
            print(f"   📍 {sig.get('index')}: {sig.get('symbol')} ({sig.get('option_type')})")
            print(f"      - Quality: {sig.get('quality_score', sig.get('confirmation_score', 'N/A'))}%")
            print(f"      - Entry: {sig.get('entry_price')}, Target: {sig.get('target')}, SL: {sig.get('stop_loss')}")
    else:
        print(f"\n❌ NO STOCK SIGNALS FOUND!")
    
    if error_signals:
        print(f"\n⚠️  ERROR SIGNALS:")
        for sig in error_signals:
            print(f"   - {sig.get('index')}: {sig.get('error')}")
            if sig.get('detail'):
                print(f"     Detail: {sig.get('detail')}")
    
    print("\n" + "=" * 80)
    print("TEST 2: Check signal_type field on each signal")
    print("=" * 80)
    
    signals_with_type = [s for s in signals if 'signal_type' in s and not s.get('error')]
    signals_without_type = [s for s in signals if 'signal_type' not in s and not s.get('error')]
    
    print(f"   - Signals WITH signal_type field: {len(signals_with_type)}")
    print(f"   - Signals WITHOUT signal_type field: {len(signals_without_type)}")
    
    if signals_without_type:
        print(f"\n⚠️  WARNING: Some signals missing signal_type field:")
        for sig in signals_without_type[:3]:
            print(f"   {sig.get('symbol')} (index: {sig.get('index')})")
    
    print("\n" + "=" * 80)
    print("TEST 3: Check signal structure")
    print("=" * 80)
    
    sample_signals = [s for s in signals if not s.get('error')][:3]
    for sig in sample_signals:
        print(f"\n📋 Sample signal: {sig.get('symbol')}")
        print(f"   - index: {sig.get('index')}")
        print(f"   - signal_type: {sig.get('signal_type')}")
        print(f"   - option_type: {sig.get('option_type')}")
        print(f"   - quality_score: {sig.get('quality_score')}")
        print(f"   - confidence: {sig.get('confidence')}")
        print(f"   - Keys present: {list(sig.keys())[:10]}...")
    
    print("\n" + "=" * 80)
    print("TEST 4: Count unique symbols")
    print("=" * 80)
    
    valid_signals = [s for s in signals if not s.get('error')]
    indices = set(s.get('index') for s in valid_signals)
    print(f"   - Unique index/stock symbols: {len(indices)}")
    print(f"   - Symbols: {sorted(indices)}")

if __name__ == "__main__":
    try:
        asyncio.run(test_stock_signals())
        print("\n✅ Debug test completed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
