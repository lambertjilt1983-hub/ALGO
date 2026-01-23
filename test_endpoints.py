#!/usr/bin/env python
"""Test all 11 backend endpoints"""
import requests
import json
import time

BASE_URL = "http://localhost:8003"

endpoints = [
    ("GET", "/health", None),
    ("GET", "/autotrade/mode", None),
    ("POST", "/autotrade/toggle?enabled=true", None),
    ("GET", "/autotrade/status", None),
    ("POST", "/autotrade/mode?demo_mode=true", None),
    ("POST", "/autotrade/analyze?symbol=NIFTY&balance=100000", None),
    ("GET", "/autotrade/trades/active", None),
    ("GET", "/autotrade/debug/source", None),
    ("GET", "/autotrade/trades/history", None),
    ("GET", "/autotrade/market/indices", None),
    ("POST", "/autotrade/execute?symbol=NIFTY&price=25000", None),
]

passed = 0
failed = 0

print("=" * 60)
print("TESTING ALL 11 BACKEND ENDPOINTS")
print("=" * 60)
print()

for idx, (method, endpoint, body) in enumerate(endpoints, 1):
    url = BASE_URL + endpoint
    try:
        if method == "GET":
            response = requests.get(url, timeout=20)
        else:
            response = requests.post(url, json=body, timeout=20)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if "signals_count" in data:
                    print(f"✓ {idx:2d}. {method:4s} {endpoint:45s} - signals={data.get('signals_count')}, demos={len(data.get('demo_trades', []))}")
                elif "is_demo_mode" in data:
                    print(f"✓ {idx:2d}. {method:4s} {endpoint:45s} - demo={data.get('is_demo_mode')}")
                elif "enabled" in data:
                    print(f"✓ {idx:2d}. {method:4s} {endpoint:45s} - enabled={data.get('enabled')}")
                else:
                    print(f"✓ {idx:2d}. {method:4s} {endpoint:45s} - OK")
            except:
                print(f"✓ {idx:2d}. {method:4s} {endpoint:45s} - OK")
            passed += 1
        else:
            print(f"✗ {idx:2d}. {method:4s} {endpoint:45s} - HTTP {response.status_code}: {response.text[:100]}")
            failed += 1
    except Exception as e:
        print(f"✗ {idx:2d}. {method:4s} {endpoint:45s} - {str(e)[:50]}")
        failed += 1

print()
print("=" * 60)
print(f"RESULTS: {passed}/11 PASSED, {failed}/11 FAILED")
print("=" * 60)
