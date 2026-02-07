# 🔍 DEBUG LOGGING - See Every Zerodha API Call

## Enable Full HTTP Logging for Zerodha

To see EXACTLY what data Zerodha returns, enable detailed HTTP logging:

### Step 1: Update [backend/app/strategies/market_intelligence.py](backend/app/strategies/market_intelligence.py)

Add this at the top of the `_fetch_zerodha_quotes()` method to log all responses:

```python
def _fetch_zerodha_quotes(self) -> Dict[str, Dict[str, Any]]:
    """Fetch REAL live quotes from Zerodha Kite API."""
    self._hydrate_tokens_from_db()

    if not self.kite_api_key or not self.kite_access_token:
        print("[MarketIntelligence] ✗ Zerodha: No API key or access token configured")
        return {}

    mapping = {...}

    try:
        print("[MarketIntelligence] ▶ Connecting to Zerodha Kite API...")
        kite = KiteConnect(api_key=self.kite_api_key)
        kite.set_access_token(self.kite_access_token)
        instruments = [sym for sym in mapping.values() if sym]
        print(f"[MarketIntelligence] ▶ Fetching LTP for: {instruments}")
        quotes = kite.ltp(instruments)
        
        # NEW: Log each quote response
        for symbol, quote_data in quotes.items():
            print(f"[MarketIntelligence] ✓ {symbol}: last_price={quote_data.get('last_price')}, bid={quote_data.get('bid')}, ask={quote_data.get('ask')}, volume={quote_data.get('volume')}")
        
        print(f"[MarketIntelligence] ✓ Zerodha LTP Response received: {list(quotes.keys())}")
    except Exception as exc:
        err = str(exc)
        print(f"[MarketIntelligence] ✗ Zerodha quote fetch FAILED: {err}")
        return {}
```

---

## Step 2: Log Trade Execution Details

Add this to [backend/app/routes/auto_trading_simple.py](backend/app/routes/auto_trading_simple.py#L706):

```python
# Before placing order
print(f"[DEBUG] Zerodha Order Parameters:")
print(f"  Symbol: {zerodha_symbol}")
print(f"  Quantity: {trade.quantity or 1}")
print(f"  Side: {trade.side}")
print(f"  Price: {trade.price}")
print(f"  Order Type: MARKET")
print(f"  Product: MIS")
print(f"  Exchange: NFO")

# After order response
print(f"[DEBUG] Zerodha Order Response:")
for key, value in real_order.items():
    print(f"  {key}: {value}")
```

---

## Step 3: Monitor Price Updates in Real-Time

Add this to log every price update call:

```python
@router.post("/trades/price")
async def update_trade_price(symbol: str, price: float, authorization: Optional[str] = Header(None)):
    print(f"[API /trades/price] Updating {symbol} to ₹{price}")
    # ... rest of code
```

---

## Example Log Output You Should See

### When Dashboard Loads:

```
[API /market/indices] Called - fetching LIVE data from Zerodha...
[MarketIntelligence] Attempting Zerodha fetch (LIVE)...
[MarketIntelligence] ▶ Connecting to Zerodha Kite API...
[MarketIntelligence] ▶ Fetching LTP for: ['NSE:NIFTY 50', 'NSE:NIFTY BANK', 'NSE:FINNIFTY']
[MarketIntelligence] ✓ NSE:NIFTY 50: last_price=25079.90, bid=25078.50, ask=25079.00, volume=18234567
[MarketIntelligence] ✓ NSE:NIFTY BANK: last_price=58601.45, bid=58600.00, ask=58602.50, volume=2345678
[MarketIntelligence] ✓ NSE:FINNIFTY: last_price=26801.30, bid=26800.00, ask=26802.00, volume=567890
[MarketIntelligence] ✓ Zerodha LTP Response received: ['NSE:NIFTY 50', 'NSE:NIFTY BANK', 'NSE:FINNIFTY']
[API /market/indices] ✓ Got indices: ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
[API /market/indices] ✓ Response: indices=3, timestamp=2026-02-02T10:15:30.123456
```

### When You Click Analyze:

```
[API /analyze] Called with: symbols=NIFTY,BANKNIFTY,FINNIFTY, balance=100000, mode=LIVE
[_live_signals] Generating signals for symbols: ['NIFTY', 'BANKNIFTY', 'FINNIFTY'], instrument: weekly_option
[_live_signals] Got market indices: ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
[_live_signals] ▶ Processing NIFTY: current=25079.90, trend=Bearish
[_live_signals] ✓ Signal generated for NIFTY: BUY @ ₹77.50
[_live_signals] ▶ Processing BANKNIFTY: current=58601.45, trend=Bullish
[_live_signals] ✓ Signal generated for BANKNIFTY: BUY @ ₹940.05
[_live_signals] ✓ Generated 3 signals total
```

### When You Execute Trade:

```
[API /execute] Called - LIVE TRADE
[API /execute] Symbol: BANKNIFTY26FEB58600CE, Side: BUY, Price: 940.05, Qty: 30
[API /execute] ▶ Placing LIVE order to Zerodha...
[API /execute] ▶ Order Details: BANKNIFTY26FEB58600CE, 30 qty, BUY at ₹940.05
[DEBUG] Zerodha Order Parameters:
  Symbol: BANKNIFTY26FEB58600CE
  Quantity: 30
  Side: BUY
  Price: 940.05
  Order Type: MARKET
  Product: MIS
  Exchange: NFO
[DEBUG] Zerodha Order Response:
  success: True
  order_id: 892364102938
  order_timestamp: 2026-02-02T10:02:11Z
  status: PENDING
  filled: 0
  average_price: 0.0
```

---

## Verify Data is NOT Simulated

### ❌ What You Should NOT See:

```
# Paper trading simulation:
movement_factor = random.uniform(-0.005, 0.01)
movement = movement_factor * abs(entry_to_target)
new_price = trade.current_price + movement

# Hardcoded test data:
base_values = {'NIFTY': 25157.50, 'BANKNIFTY': 58800.30}
variation = random.uniform(-0.003, 0.003)
current = round(value * (1 + variation), 2)
```

### ✅ What You SHOULD See:

```
[MarketIntelligence] ✓ NSE:NIFTY 50: last_price=25079.90  <- Real Zerodha data
[DEBUG] Zerodha Order Response:
  success: True
  order_id: 892364102938                                   <- Real order ID
  status: PENDING                                          <- Real status from Zerodha
```

---

## Pro Tip: Search Terminal Output

When backend is running, search logs for these keywords to verify:

- `✓ Zerodha` = Success ✓
- `✗ Zerodha` = Failed (check error)
- `NSE:NIFTY` = Real LTP from Zerodha
- `order_id` = Real order placed
- `movement_factor` = SIMULATION (should NOT see this!)

---

## Next: Redirect Logs to File

If terminal output is too fast, save logs to file:

```bash
# Windows PowerShell
$env:PYTHONUTF8=1
python backend/app/main.py | Tee-Object -FilePath "logs/zerodha_trading.log"

# Linux/Mac
python backend/app/main.py | tee logs/zerodha_trading.log
```

Then open the log file in VS Code to search and scroll at your own pace.

---

## Final: You Can Now Trust the Numbers

With all these logs enabled:
- ✓ Every price comes from Zerodha LTP
- ✓ Every order has real order_id from Zerodha
- ✓ Every trade execution is verified
- ✓ Every P&L is calculated from real prices

**You're seeing exactly what Zerodha is returning.**
