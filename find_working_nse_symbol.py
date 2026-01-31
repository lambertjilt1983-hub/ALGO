import json
import datetime
from kiteconnect import KiteConnect

# --- CONFIG ---
API_KEY = "YOUR_API_KEY"  # Replace with your API key
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"  # Replace with your access token
INSTRUMENTS_CACHE = "backend/instruments_cache.json"  # Path to your cache
INTERVALS = ["5minute", "15minute", "30minute", "1day"]
LOOKBACK = 100

# --- INIT ---
kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

with open(INSTRUMENTS_CACHE, "r", encoding="utf-8") as f:
    instruments = json.load(f)

nse_instruments = [
    ins for ins in instruments
    if ins.get("exchange") == "NSE" and ins.get("instrument_type") in ("EQ", "INDEX")
]

print(f"Loaded {len(nse_instruments)} NSE instruments.")

now = datetime.datetime.now()
from_date = now - datetime.timedelta(days=LOOKBACK)
to_date = now

for interval in INTERVALS:
    print(f"\nTrying interval: {interval}")
    for ins in nse_instruments:
        symbol = f"NSE:{ins['tradingsymbol']}"
        token = ins["instrument_token"]
        try:
            data = kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            if data:
                print(f"SUCCESS: {symbol} (token={token}) interval={interval} count={len(data)}")
                print("Sample:", data[:2])
                exit(0)
            else:
                print(f"No data: {symbol} interval={interval}")
        except Exception as e:
            print(f"ERROR: {symbol} interval={interval} - {e}")

print("No working symbol found. Try increasing LOOKBACK or check your API credentials.")
