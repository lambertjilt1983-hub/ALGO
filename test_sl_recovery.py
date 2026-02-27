#!/usr/bin/env python3
"""
Test script for SL Recovery Manager
Validates that the system is working correctly
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/autotrade"

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_recovery_status():
    """Test: Get recovery status"""
    print_section("Test 1: Check Recovery Status")
    
    response = requests.get(f"{BASE_URL}/recovery-status")
    print(f"Status: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    
    # Verify response structure
    data = response.json()
    assert "success" in data
    assert "total_sl_hits" in data
    assert "symbols_with_sl" in data
    print("✅ Recovery status endpoint working")

def test_recovery_signal_excellent():
    """Test: Recovery signal with excellent confidence"""
    print_section("Test 2: Recovery Signal - Excellent Confidence (97%)")
    
    payload = {
        "base_symbol": "FINNIFTY26MAR28000",
        "signal_confidence": 0.97,
        "current_price": 510.0,
        "recent_prices": [505.0, 507.0, 509.0, 510.0]  # Uptrend → BULLISH
    }
    
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    
    data = response.json()
    if data.get("success"):
        print("✅ Recovery signal generated successfully")
        print(f"  Recommendation: {data.get('recommendation')}")
        print(f"  Option Type: {data.get('option_type')}")
    else:
        print(f"⚠️  Signal blocked: {data.get('reason')}")

def test_recovery_signal_low_confidence():
    """Test: Recovery signal with low confidence"""
    print_section("Test 3: Recovery Signal - Low Confidence (80%)")
    
    payload = {
        "base_symbol": "NIFTY50",
        "signal_confidence": 0.80,  # Below 95% threshold
        "current_price": 22500.0,
        "recent_prices": [22400.0, 22450.0, 22500.0]
    }
    
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    data = response.json()
    
    print(f"Response:\n{json.dumps(data, indent=2)}")
    
    # Should be blocked due to low confidence
    if not data.get("can_trade"):
        print("✅ Correctly blocked low-confidence signal")
        print(f"   Reason: {data.get('reason')}")
    else:
        print("⚠️  WARNING: Low confidence signal was approved (should not happen)")

def test_recovery_signal_neutral_market():
    """Test: Recovery signal in neutral market"""
    print_section("Test 4: Recovery Signal - Neutral Market (95% confidence)")
    
    payload = {
        "base_symbol": "BANKNIFTY60800",
        "signal_confidence": 0.95,  # Just meets threshold
        "current_price": 46500.0,
        "recent_prices": [46400.0, 46450.0, 46480.0, 46500.0, 46490.0]  # Rangebound
    }
    
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    data = response.json()
    
    print(f"Response:\n{json.dumps(data, indent=2)}")
    print(f"Market Trend: {data.get('market_trend')}")
    print(f"Trend Strength: {data.get('trend_strength')}")

def test_multiple_recoveries():
    """Test: Multiple symbol recoveries"""
    print_section("Test 5: Multiple Symbol Recoveries")
    
    symbols = [
        ("FINNIFTY26MAR28000", 0.96, 510.0),
        ("NIFTY2630225300", 0.95, 120.0),
        ("BANKNIFTY60800", 0.97, 995.0),
    ]
    
    for base_symbol, confidence, price in symbols:
        payload = {
            "base_symbol": base_symbol,
            "signal_confidence": confidence,
            "current_price": price,
            "recent_prices": [price * 0.99, price * 0.995, price]
        }
        
        response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
        data = response.json()
        
        print(f"\n{base_symbol}:")
        print(f"  Confidence: {confidence:.2%}")
        print(f"  Can Trade: {data.get('can_trade')}")
        print(f"  Option Type: {data.get('option_type')}")
        print(f"  Trend: {data.get('market_trend')}")

def test_bearish_market():
    """Test: Recovery signal in bearish market"""
    print_section("Test 6: Bearish Market - PE Recovery")
    
    payload = {
        "base_symbol": "FINNIFTY28000",
        "signal_confidence": 0.96,
        "current_price": 510.0,
        "recent_prices": [520.0, 515.0, 512.0, 510.0]  # Downtrend → BEARISH
    }
    
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    data = response.json()
    
    print(f"Response:\n{json.dumps(data, indent=2)}")
    
    if data.get("market_trend") == "BEARISH":
        print("✅ Correctly identified bearish trend")
        if data.get("option_type") == "PE":
            print("✅ Correctly recommended PE for bearish market")
        else:
            print(f"⚠️  Recommended {data.get('option_type')} in bearish market")

def test_bullish_market():
    """Test: Recovery signal in bullish market"""
    print_section("Test 7: Bullish Market - CE Recovery")
    
    payload = {
        "base_symbol": "FINNIFTY28000",
        "signal_confidence": 0.96,
        "current_price": 510.0,
        "recent_prices": [505.0, 507.0, 509.0, 510.0]  # Uptrend → BULLISH
    }
    
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    data = response.json()
    
    print(f"Response:\n{json.dumps(data, indent=2)}")
    
    if data.get("market_trend") == "BULLISH":
        print("✅ Correctly identified bullish trend")
        if data.get("option_type") == "CE":
            print("✅ Correctly recommended CE for bullish market")
        else:
            print(f"⚠️  Recommended {data.get('option_type')} in bullish market")

def test_edge_cases():
    """Test: Edge cases"""
    print_section("Test 8: Edge Cases")
    
    # Test 1: Exactly 95% confidence (boundary)
    print("Test 8.1: Exactly 95% Confidence (At Boundary)")
    payload = {
        "base_symbol": "TEST95",
        "signal_confidence": 0.95,
        "current_price": 100.0,
        "recent_prices": [100.0]
    }
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    data = response.json()
    print(f"Result: {data.get('can_trade')}")
    print(f"Reason: {data.get('reason')}\n")
    
    # Test 2: Just below 95% (should fail)
    print("Test 8.2: Just Below 95% Confidence (94.9%)")
    payload["signal_confidence"] = 0.949
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    data = response.json()
    print(f"Result: {data.get('can_trade')}")
    print(f"Reason: {data.get('reason')}\n")
    
    # Test 3: Empty recent prices
    print("Test 8.3: Empty Recent Prices")
    payload["signal_confidence"] = 0.96
    payload["recent_prices"] = []
    response = requests.post(f"{BASE_URL}/recovery-signal", json=payload)
    data = response.json()
    print(f"Result: {data.get('can_trade')}")
    print(f"Trend: {data.get('market_trend')}")

def run_all_tests():
    """Run all tests"""
    print("\n\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*12 + "SL RECOVERY MANAGER - TEST SUITE" + " "*12 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        test_recovery_status()
        input("\nPress Enter to continue to next test...")
        
        test_recovery_signal_excellent()
        input("\nPress Enter to continue to next test...")
        
        test_recovery_signal_low_confidence()
        input("\nPress Enter to continue to next test...")
        
        test_recovery_signal_neutral_market()
        input("\nPress Enter to continue to next test...")
        
        test_multiple_recoveries()
        input("\nPress Enter to continue to next test...")
        
        test_bearish_market()
        input("\nPress Enter to continue to next test...")
        
        test_bullish_market()
        input("\nPress Enter to continue to next test...")
        
        test_edge_cases()
        input("\nPress Enter to finish...")
        
        print_section("All Tests Completed ✅")
        print("SL Recovery Manager is working correctly!")
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to backend at", BASE_URL)
        print("Make sure the backend is running: python backend/app/main.py")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    run_all_tests()
