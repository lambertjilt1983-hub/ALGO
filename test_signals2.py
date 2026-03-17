#!/usr/bin/env python
"""Quick test to check backend signals and stock filtering"""
import requests
import json

try:
    url = 'http://localhost:8000/autotrade/analyze'
    params = {
        'symbols': 'NIFTY,FINNIFTY,BANKNIFTY,SBIN,TCS,RELIANCE',
        'instrument_type': 'monthly_option',
        'quantity': '50',
        'balance': '100000',
        'test_bypass_market_check': 'true'  # DEBUG: bypass market hours check
    }
    
    print("Fetching signals from backend...")
    resp = requests.post(url, params=params, timeout=10)
    data = resp.json()
    
    # Check if market is open
    if 'detail' in data:
        print(f"❌ Market/API Error: {data['detail'].get('message', data['detail'])}")
        print(f"   Current time: {data['detail'].get('current_time')}")
        import sys
        sys.exit(1)
    
    signals = data.get('signals', [])
    ai_rejected = data.get('ai_rejected_recommendations', [])
    
    print(f"\n📊 Backend Response:")
    print(f"  ✓ Accepted signals: {len(signals)}")
    print(f"  ⚠ AI rejected: {len(ai_rejected)}")
    
    # Filter by type
    indices_sigs = [s for s in signals if s.get('signal_type') == 'index' or not s.get('is_stock')]
    stocks_sigs = [s for s in signals if s.get('signal_type') == 'stock' or s.get('is_stock')]
    
    print(f"\n📈 ACCEPTED - INDICES: {len(indices_sigs)}")
    if indices_sigs:
        print(f"{'Symbol':<20} {'Quality':>10} {'Confidence':>12} {'RR':>8}")
        print("-" * 50)
        for s in indices_sigs[:5]:
            q = s.get('quality_score', 0)
            c = s.get('confirmation_score', s.get('confidence', 0))
            rr = s.get('rr', 0)
            print(f"{s.get('symbol', 'N/A'):<20} {q:>9.1f}%  {c:>11.1f}%  {rr:>7.2f}")
    
    print(f"\n📊 ACCEPTED - STOCKS: {len(stocks_sigs)}")
    if stocks_sigs:
        print(f"{'Symbol':<20} {'Quality':>10} {'Confidence':>12} {'RR':>8}")
        print("-" * 50)
        for s in stocks_sigs[:5]:
            q = s.get('quality_score', 0)
            c = s.get('confirmation_score', s.get('confidence', 0))
            rr = s.get('rr', 0)
            print(f"{s.get('symbol', 'N/A'):<20} {q:>9.1f}%  {c:>11.1f}%  {rr:>7.2f}")
    else:
        print("⚠️  No stock signals accepted")
    
    # Show why stocks are rejected
    rejected_stocks = [r for r in ai_rejected if r.get('signal_type') == 'stock']
    if rejected_stocks:
        print(f"\n🚫 REJECTED - STOCKS ({len(rejected_stocks)} total):")
        for r in rejected_stocks[:3]:
            print(f"\n  {r.get('symbol')}:")
            print(f"    Reason: {r.get('reason')}")
            print(f"    Details: {r.get('details', [])}")
            details = r.get('quality_gate_details', {})
            if details:
                print(f"    Quality: {details.get('quality_score', '?')} (min: {details.get('quality_min', '?')})")
                print(f"    Confirmation: {details.get('confirmation_score', '?')} (min: {details.get('confirmation_min', '?')})")
                print(f"    AI Edge: {details.get('ai_edge_score', '?')} (min: {details.get('ai_edge_min', '?')})")
            
except Exception as e:
    import traceback
    print(f"❌ Error: {e}")
    traceback.print_exc()

