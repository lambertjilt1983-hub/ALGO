#!/usr/bin/env python3
"""
Test IST timezone handling in trade times
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_timezone_handling():
    """Test that exit_time and entry_time include proper timezone info"""
    from app.core.market_hours import _market_tz
    
    print("=" * 60)
    print("TIMEZONE HANDLING TEST")
    print("=" * 60)
    print()
    
    # Test 1: Create IST time
    print("[1] Creating IST time with _market_tz()...")
    market_tz = _market_tz()
    print(f"  Market TZ: {market_tz}")
    
    ist_now = datetime.now(tz=market_tz)
    print(f"  IST Now: {ist_now}")
    print(f"  IST ISO: {ist_now.isoformat()}")
    print()
    
    # Test 2: Naive datetime conversion
    print("[2] Converting naive datetime to IST...")
    naive_dt = datetime.utcnow()
    print(f"  Naive UTC: {naive_dt}")
    
    # Add IST timezone to naive datetime (doesn't change the time, just adds timezone info)
    with_tz = naive_dt.replace(tzinfo=market_tz)
    print(f"  With IST TZ: {with_tz}")
    print(f"  ISO Format: {with_tz.isoformat()}")
    print()
    
    # Test 3: Check timezone offset
    print("[3] Checking IST offset...")
    if "+" in with_tz.isoformat():
        print(f"  ✓ Timezone offset present in ISO string")
        # Extract offset
        iso_str = with_tz.isoformat()
        if "+05:30" in iso_str:
            print(f"  ✓ Correct IST offset (+05:30)")
        else:
            print(f"  ✗ Incorrect offset: {iso_str[-6:]}")
    else:
        print(f"  ✗ No timezone offset in ISO string")
    print()
    
    # Test 4: Parse and re-serialize
    print("[4] Parse and re-serialize roundtrip...")
    iso_with_tz = with_tz.isoformat()
    parsed = datetime.fromisoformat(iso_with_tz)
    re_serialized = parsed.isoformat()
    print(f"  Original ISO: {iso_with_tz}")
    print(f"  Re-serialized: {re_serialized}")
    if iso_with_tz == re_serialized:
        print(f"  ✓ Roundtrip successful")
    else:
        print(f"  ✗ Roundtrip failed")
    print()
    
    # Test 5: Database simulation
    print("[5] Simulating database storage and retrieval...")
    from app.core.database import SessionLocal
    from app.models.trading import TradeReport
    
    try:
        db = SessionLocal()
        
        # Get most recent trade from database
        recent_trade = db.query(TradeReport).order_by(TradeReport.exit_time.desc()).first()
        
        if recent_trade:
            print(f"  Recent trade: {recent_trade.symbol}")
            print(f"  Exit time from DB: {recent_trade.exit_time}")
            print(f"  Type: {type(recent_trade.exit_time)}")
            print(f"  Has tzinfo: {recent_trade.exit_time.tzinfo is not None}")
            
            # Simulate the fix
            if recent_trade.exit_time.tzinfo is None:
                market_tz = _market_tz()
                fixed_time = recent_trade.exit_time.replace(tzinfo=market_tz)
                print(f"  Fixed time: {fixed_time}")
                print(f"  Fixed ISO: {fixed_time.isoformat()}")
                if "+05:30" in fixed_time.isoformat():
                    print(f"  ✓ Fix adds IST timezone correctly")
            else:
                print(f"  ✓ Time already has timezone info")
        else:
            print(f"  No trades in database to test")
        
        db.close()
    except Exception as e:
        print(f"  Error accessing database: {e}")
    
    print()
    print("=" * 60)
    print("TIMEZONE TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_timezone_handling()
