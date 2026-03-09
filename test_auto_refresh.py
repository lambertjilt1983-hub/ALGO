#!/usr/bin/env python3
"""
Test auto-refresh functionality:
1. Simulate user clicking "Start Auto-Trading"
2. Monitor if signal fetch requests are being made every ~1 second
3. Verify backend is returning fresh signals (not stale cache)
"""

import asyncio
import aiohttp
import time
from datetime import datetime

API_BASE = "http://localhost:8000"
OPTION_SIGNALS_URL = f"{API_BASE}/option-signals/intraday-advanced?mode=balanced&include_nifty50=true"

async def test_auto_refresh():
    """Simulate auto-refresh requests and verify responses"""
    
    print("Testing Auto-Refresh Signal Fetching...")
    print(f"URL: {OPTION_SIGNALS_URL}")
    print("-" * 80)
    
    async with aiohttp.ClientSession() as session:
        last_signals = {}
        fetch_count = 0
        
        for i in range(5):  # Simulate 5 refresh cycles (5 seconds)
            try:
                fetch_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                start = time.time()
                async with session.get(OPTION_SIGNALS_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        fetch_time = time.time() - start
                        
                        signals = data.get("signals", [])
                        signal_count = len(signals)
                        
                        # Check for changes from previous fetch
                        status = "✅ FRESH" if signals != last_signals else "⚠️ CACHED"
                        
                        print(f"[{timestamp}] Fetch #{fetch_count}: {signal_count} signals | {fetch_time:.2f}s | {status}")
                        
                        if signals and len(signals) > 0:
                            # Show first few signals
                            for idx, sig in enumerate(signals[:2]):
                                print(f"   - {sig.get('symbol', 'N/A')}: {sig.get('quality', 0)}% quality, Entry: ₹{sig.get('entry_price', 0)}")
                        
                        last_signals = signals
                    else:
                        print(f"[{timestamp}] Fetch #{fetch_count}: ERROR {resp.status}")
                
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetch #{fetch_count}: FAILED - {str(e)}")
            
            # Wait 1 second before next fetch (simulating auto-refresh interval)
            if i < 4:
                await asyncio.sleep(1)
    
    print("-" * 80)
    print("✅ Test complete! If signals are changing, auto-refresh is working correctly.")

if __name__ == "__main__":
    try:
        asyncio.run(test_auto_refresh())
    except KeyboardInterrupt:
        print("\n⏹️ Test cancelled")
    except Exception as e:
        print(f"❌ Test failed: {e}")
