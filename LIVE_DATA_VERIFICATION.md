# ✅ LIVE DATA VERIFICATION GUIDE
## Zerodha Real Market Data - No Simulation

### 🔴 WHAT YOU NEED TO VERIFY

You're now running **100% LIVE** - all data comes from Zerodha when connected. Follow this guide to confirm each step.

---

## 📊 STEP 1: Check Market Data Source

When you load the dashboard or click "📊 Analyze", check the **backend logs** for:

```
[MarketIntelligence] Attempting Zerodha fetch (LIVE)...
[MarketIntelligence] ✓ Zerodha data fetched: ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
[MarketIntelligence] ▶ Connecting to Zerodha Kite API...
[MarketIntelligence] ▶ Fetching LTP for: ['NSE:NIFTY 50', 'NSE:NIFTY BANK', 'NSE:FINNIFTY']
[MarketIntelligence] ✓ Zerodha LTP Response received: dict_keys(['NSE:NIFTY 50', 'NSE:NIFTY BANK', 'NSE:FINNIFTY'])
```

### ✅ If you see this: 
- Zerodha is connected ✓
- Prices are REAL ✓
- No simulation/fallback ✓

### ⚠️ If you see this instead:
```
[MarketIntelligence] ✗ Zerodha: No API key or access token configured
[MarketIntelligence] ⚠ Zerodha unavailable, trying NSE...
```
- Zerodha not connected
- Falling back to NSE (still real data, not simulated)
- Check your broker credentials

---

## 🎯 STEP 2: Monitor Market Indices Endpoint

When `/autotrade/market/indices` is called (every time dashboard refreshes):

```
[API /market/indices] Called - fetching LIVE data from Zerodha...
[API /market/indices] ✓ Got indices: ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
[API /market/indices] ✓ Response: indices=3, timestamp=2026-02-02T10:15:30.123456
```

**Response should include:**
```json
{
  "indices": [
    {
      "symbol": "NIFTY",
      "price": 25079.50,        // REAL price from Zerodha
      "change_pct": -0.30,      // REAL change
      "trend": "Bearish",       // REAL analysis
      "source": "zerodha_live"  // ✓ Zerodha source
    }
  ],
  "source": "zerodha"           // ✓ NOT "simulated"
}
```

---

## 🚀 STEP 3: When You Click "▶ Start Auto-Trading"

Check logs for:

```
[API /execute] Called - LIVE TRADE
[API /execute] Symbol: BANKNIFTY26FEB58600CE, Side: BUY, Price: 940.05, Qty: 30
[API /execute] ▶ Placing LIVE order to Zerodha...
[API /execute] ▶ Order Details: BANKNIFTY26FEB58600CE, 30 qty, BUY at ₹940.05
[API /execute] ✓ Zerodha order ACCEPTED - Order ID: 892364102938
```

### What this means:
- ✓ Order sent to Zerodha
- ✓ Order accepted in real account
- ✓ Real money is being used
- ✓ No demo/simulation

---

## 💰 STEP 4: Monitor Active Trades

```
[API /trades/active] Returning 1 active trades from Zerodha
```

Response shows **ONLY real Zerodha trades**, not paper trades:

```json
{
  "trades": [
    {
      "id": 1,
      "symbol": "BANKNIFTY26FEB58600CE",
      "price": 940.05,           // Entry price from Zerodha
      "side": "BUY",
      "quantity": 30,
      "current_price": 945.90,   // Updated from Zerodha real-time
      "target": 965.05,
      "stop_loss": 920.05,
      "status": "OPEN",
      "timestamp": "2026-02-02T10:02:11"
    }
  ],
  "count": 1
}
```

---

## 🔄 STEP 5: Price Updates

Every time price is fetched for an active trade:

```
[MarketIntelligence] ▶ Fetching LTP for: ['NSE:BANKNIFTY']
[MarketIntelligence] ✓ Zerodha LTP Response: {'NSE:BANKNIFTY': {'last_price': 945.90, ...}}
```

✅ **NOT** like before where it was:
```
# OLD (SIMULATED):
movement = movement_factor * abs(entry_to_target)
new_price = trade.current_price + movement  # Random walk!
```

---

## 📈 STEP 6: Verify No Simulation

When market is closed, the system should **NOT**:
- Continue updating prices with random movements
- Show "LIVE" data that's actually simulated
- Use `/paper-trades/update-prices` endpoint

Instead:
- Prices stay at last known close if market closed
- No random price increments
- Only Zerodha provides data when market is open

---

## 🔍 HOW TO VIEW LOGS IN REAL-TIME

### Option 1: Terminal (while backend is running)
All logs will print to the terminal where you started the backend.

### Option 2: Check Browser Console
Open DevTools (F12) → Console tab to see API calls:
```javascript
console.log('[Dashboard] Fetching from /autotrade/market/indices...')
```

### Option 3: Create a Log File

Add this to [backend/app/main.py](backend/app/main.py) if not already there:

```python
import logging
logging.basicConfig(
    filename='logs/zerodha_trading.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## ✅ FINAL CHECKLIST

- [ ] Backend logs show `[MarketIntelligence] ✓ Zerodha data fetched`
- [ ] Market indices endpoint returns `"source": "zerodha_live"`
- [ ] When executing trade: `✓ Zerodha order ACCEPTED`
- [ ] Active trades show real Zerodha data
- [ ] Price updates come from Zerodha LTP (not random walk)
- [ ] After market close: No more price updates (not simulated)

---

## 🎯 YOU ARE NOW RUNNING:
✅ **LIVE TRADING** with **REAL ZERODHA DATA**
✅ **100% REAL PRICES** - no hardcoding or simulation
✅ **EVERY API CALL IS LOGGED** - see exactly what's happening
✅ **REAL MONEY TRADES** - when you click execute

---

## ⚡ NEXT: MONITOR YOUR FIRST TRADE

1. Keep terminal visible to see logs
2. Click "📊 Analyze" and note the Zerodha API calls in logs
3. Click "▶ Start Auto-Trading" and confirm Zerodha accepts the order
4. Watch the logs for price updates from Zerodha
5. See your real P&L calculation from actual prices

**Everything is LIVE now. Every call is real.**
