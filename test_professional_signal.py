import requests

# --- CONFIG ---
BASE_URL = "http://localhost:8000"
USERNAME = "admin"  # Change if needed
PASSWORD = "admin123"  # Change if needed
SYMBOLS = [
    "NSE:RELIANCE", "NSE:TCS", "NSE:INFY", "NSE:HDFCBANK", "NSE:ICICIBANK", "NSE:SBIN", "NSE:ITC", "NSE:LT", "NSE:AXISBANK", "NSE:KOTAKBANK"
]
INTERVAL = "day"
LOOKBACK = 200

# --- LOGIN ---
login_url = f"{BASE_URL}/auth/login"
login_data = {"username": USERNAME, "password": PASSWORD}
print("Logging in...")
resp = requests.post(login_url, json=login_data)
if resp.status_code != 200:
    print(f"Login failed: {resp.text}")
    exit(1)
token = resp.json()["access_token"]
print(f"✓ Login successful, token: {token[:20]}...")

# --- TEST MULTIPLE SYMBOLS ---
headers = {"Authorization": f"Bearer {token}"}
url = f"{BASE_URL}/strategies/live/professional-signal"
for symbol in SYMBOLS:
    params = {"symbol": symbol, "interval": INTERVAL, "lookback": LOOKBACK}
    print(f"\nRequesting: {url} with symbol={symbol} ...")
    resp = requests.get(url, headers=headers, params=params)
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
    except Exception:
        print(resp.text)
        continue
    if resp.status_code == 200 and "signal" in data:
        print(f"SUCCESS for {symbol}:")
        print(data)
        break
    else:
        print(f"No signal for {symbol}: {data}")
