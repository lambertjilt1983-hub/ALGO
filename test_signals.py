#!/usr/bin/env python
"""Quick test to check backend signals"""
import requests
import json

try:
    url = 'http://localhost:8000/autotrade/analyze'
    params = {
        'symbols': 'NIFTY,FINNIFTY,BANKNIFTY',
        'instrument_type': 'monthly_option',
        'quantity': '50',
        'balance': '100000'
    }
    
    print("Fetching signals from backend...")
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
        signals = data.get('signals', [])
    high_confidence = data.get('high_confidence_signals', [])
    ai_rejected = data.get('ai_rejected_recommendations', [])
    blocked_recs = data.get('blocked_recommendations', [])
    
    print(f"✓ Backend Response:")
    print(f"  - Accepted signals: {len(signals)}")
    print(f"  - High confidence: {len(high_confidence)}")
    print(f"  - AI rejected: {len(ai_rejected)}")
    print(f"  - Blocked: {len(blocked_recs)}")
    print(f"  - Total scanned: {data.get('signals_count', '?')}\n")
    
    if ai_rejected and not signals:
        print("⚠️ All signals were REJECTED by quality gates:\n")
        for rej in ai_rejected[:5]:
            print(f"  Symbol: {rej.get('symbol')}")
            print(f"  Reason: {rej.get('reason')}")
            details = rej.get('quality_gate_details', {})
            if details:
                print(f"    Quality: {details.get('quality_score', '?')} (min: {details.get('quality_min', '?')})")
                print(f"    Confirmation: {details.get('confirmation_score', '?')} (min: {details.get('confirmation_min', '?')})")
                print(f"    AI Edge: {details.get('ai_edge_score', '?')} (min: {details.get('ai_edge_min', '?')})")
                print(f"    Daily trades: {details.get('daily_trades_count', '?')} / {details.get('max_daily_trades', '?')}")
                print(f"    Consecutive SL: {details.get('consecutive_sl_count', '?')} / {details.get('consecutive_sl_limit', '?')}")
            print()
    
    if signals:
        print(f"{'Symbol':<30} {'Quality':>10} {'Confidence':>12} {'RR':>8} {'Start':>8}")
        print("=" * 70)
        for sig in signals[:10]:
            quality = sig.get('quality_score', sig.get('quality', 0))
            confidence = sig.get('confirmation_score', sig.get('confidence', 0))
            rr = sig.get('rr', 0)
            entry_ok = 'YES' if sig.get('entry_valid') or sig.get('ai_valid') else 'NO'
            print(f"{sig.get('symbol', 'N/A'):<30} {quality:>9.1f}%  {confidence:>11.1f}%  {rr:>7.2f}  {entry_ok:>8}")
    else:
        print("❌ No signals returned!")
        if data.get('ai_rejected_recommendations'):
            print(f"\n⚠ {len(data['ai_rejected_recommendations'])} signals were REJECTED by quality gates:")
            for rej in data['ai_rejected_recommendations'][:3]:
                print(f"  - {rej.get('symbol')}: {rej.get('reason')} - {rej.get('details', [])}")
                
except Exception as e:
    print(f"❌ Error: {e}")
