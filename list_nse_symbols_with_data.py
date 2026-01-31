import json
import datetime
from kiteconnect import KiteConnect
import os


# Load API key from env or hardcode
API_KEY = os.getenv("ZERODHA_API_KEY", "30i4qnng2thn7mfd")

# Load access token from DB
import sqlite3
import sys
import os
 # Dynamically add the backend/app directory to sys.path for 'app' import
backend_app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend', 'app'))
if backend_app_path not in sys.path:
    sys.path.insert(0, backend_app_path)
from app.core.security import encryption_manager
conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()
c.execute('SELECT access_token FROM broker_credentials WHERE broker_name = ? AND is_active = 1 ORDER BY id DESC LIMIT 1', ('zerodha',))
row = c.fetchone()
conn.close()

if not row:
    print("No access token found in DB.")
    exit(1)
print(f"[DEBUG] Raw access token from DB: {row[0]}")
try:
    ACCESS_TOKEN = encryption_manager.decrypt_credentials(row[0])
    print(f"[DEBUG] Decrypted access token: {ACCESS_TOKEN}")
except Exception as e:
    print(f"[WARN] Could not decrypt access token, using raw token: {e}")
    ACCESS_TOKEN = row[0]

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

# Load cached instruments
with open("instruments_cache.json", "r", encoding="utf-8") as f:
    instruments = json.load(f)

# Test for recent data (last 5 days, 1day interval)
from_date = datetime.datetime.now() - datetime.timedelta(days=5)
to_date = datetime.datetime.now()

print("symbol,exchange,tradingsymbol,token,ohlcv_count")
count = 0
for i in instruments:
    if i.get("exchange") == "NSE":
        symbol = f"NSE:{i['tradingsymbol']}"
        token = i["instrument_token"]
        try:
            ohlcv = kite.historical_data(token, from_date, to_date, "day")
            if ohlcv:
                print(f"{symbol},NSE,{i['tradingsymbol']},{token},{len(ohlcv)}")
                count += 1
                if count >= 10:
                    break
        except Exception as e:
            continue
