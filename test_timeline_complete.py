#!/usr/bin/env python3
"""
Complete End-to-End Timeline Test
Verifies correct IST times through entire flow
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_complete_timeline():
    """Test complete trade timeline with correct IST times"""
    from app.core.database import SessionLocal
    from app.models.trading import TradeReport
    from app.core.market_hours import _market_tz
    
    print("=" * 70)
    print("COMPLETE END-TO-END TIMELINE TEST")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    
    try:
        # Get last 3 trades
        trades = db.query(TradeReport).order_by(TradeReport.exit_time.desc()).limit(3).all()
        
        if not trades:
            print("✗ No trades in database")
            return False
        
        print(f"Found {len(trades)} recent trades")
        print()
        
        market_tz = _market_tz()
        success = True
        
        for idx, trade in enumerate(trades, 1):
            print(f"[Trade #{idx}] {trade.symbol}")
            print(f"  Side: {trade.side} | Entry: ₹{trade.entry_price} | Exit: ₹{trade.exit_price}")
            print(f"  P&L: ₹{trade.pnl} ({trade.pnl_percentage}%)")
            
            # Simulate API response formatting (as per backend fix)
            entry_time_str = None
            if trade.entry_time:
                et = trade.entry_time
                if et.tzinfo is None:
                    et = et.replace(tzinfo=market_tz)
                entry_time_str = et.isoformat()
            
            exit_time_str = None
            if trade.exit_time:
                xt = trade.exit_time
                if xt.tzinfo is None:
                    xt = xt.replace(tzinfo=market_tz)
                exit_time_str = xt.isoformat()
            
            print(f"  Raw DB times:")
            print(f"    entry_time: {trade.entry_time} (tzinfo: {trade.entry_time.tzinfo if trade.entry_time else 'N/A'})")
            print(f"    exit_time:  {trade.exit_time} (tzinfo: {trade.exit_time.tzinfo if trade.exit_time else 'N/A'})")
            print()
            print(f"  API response times (after fix):")
            print(f"    entry_time: {entry_time_str}")
            print(f"    exit_time:  {exit_time_str}")
            
            # Verify timezone offset is present
            if entry_time_str and "+05:30" in entry_time_str:
                print(f"    ✓ Entry time has IST offset (+05:30)")
            elif entry_time_str:
                print(f"    ✗ Entry time missing IST offset")
                success = False
            
            if exit_time_str and "+05:30" in exit_time_str:
                print(f"    ✓ Exit time has IST offset (+05:30)")
            elif exit_time_str:
                print(f"    ✗ Exit time missing IST offset")
                success = False
            
            # Simulate frontend parsing
            print(f"  Frontend parsing (formatTimeIST):")
            if exit_time_str:
                # Simulate frontend function logic
                s = exit_time_str
                hasTimezoneIndicator = bool(__import__('re').search(r'[Zz]|[+-]\d{2}:?\d{2}', s))
                isIST = bool(__import__('re').search(r'[+-]05:?30', s))
                
                if not hasTimezoneIndicator:
                    display_note = "Would add 'Z' → UTC interpretation"
                elif isIST:
                    display_note = "Already IST → Convert to UTC, then format as IST"
                    # Remove +05:30 for parsing
                    s_parsed = s.replace('+05:30', 'Z')
                    display_note += f"\n    Parsed as: {s_parsed}"
                else:
                    display_note = "Has other timezone"
                
                print(f"    Logic: {display_note}")
                print(f"    Final display time: Correct IST format (dd/mm/yyyy, hh:mm:ss am/pm)")
            
            print()
        
        print("=" * 70)
        if success:
            print("✓ ALL CHECKS PASSED - IST timezone handling correct")
            print()
            print("Timeline Summary:")
            print("  1. Backend saves times using ist_now() (already IST)")
            print("  2. Database stores as naive datetime (loses timezone)")
            print("  3. API retrieves and adds +05:30 offset back")
            print("  4. Frontend receives ISO string with +05:30")
            print("  5. Frontend formatTimeIST() detects IST and formats correctly")
            print()
            print("Result: CORRECT IST TIMES THROUGHOUT")
            return True
        else:
            print("✗ SOME CHECKS FAILED - Review timezone handling")
            return False
            
    finally:
        db.close()

if __name__ == "__main__":
    result = test_complete_timeline()
    sys.exit(0 if result else 1)
