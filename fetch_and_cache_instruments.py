import os
import json
from kiteconnect import KiteConnect

API_KEY = os.getenv("ZERODHA_API_KEY", "30i4qnng2thn7mfd")
ACCESS_TOKEN = os.getenv("ZERODHA_ACCESS_TOKEN", "c2LLp1Wp179507J20r7o8Xkv60N4UKGb")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

print("Fetching instruments from Zerodha...")
instruments = kite.instruments()
# Convert any date fields to string for JSON serialization
for inst in instruments:
    for k, v in inst.items():
        if hasattr(v, 'isoformat'):
            inst[k] = v.isoformat()
with open("instruments_cache.json", "w", encoding="utf-8") as f:
    json.dump(instruments, f)
print(f"Saved {len(instruments)} instruments to instruments_cache.json")
