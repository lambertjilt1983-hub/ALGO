# ⚡ QUICK REFERENCE - LIVE TRADING

## 🎯 What Changed

| Before | After |
|--------|-------|
| Simulated prices | ✅ Zerodha LIVE prices |
| Random walk updates | ✅ Real LTP from broker |
| Updates after market close | ✅ No updates when closed |
| Hardcoded values | ✅ 100% broker data |
| No visibility | ✅ Detailed logging on every call |

---

## 📋 Terminal Log Checklist

When everything works, you should see:

```
Dashboard Loads:
✓ [MarketIntelligence] Attempting Zerodha fetch (LIVE)...
✓ [MarketIntelligence] ✓ Zerodha data fetched: ['NIFTY', 'BANKNIFTY', 'FINNIFTY']

Click Analyze:
✓ [API /analyze] Called with: symbols=NIFTY,BANKNIFTY,FINNIFTY
✓ [_live_signals] ✓ Signal generated for NIFTY: BUY @ ₹77.50

Click Execute:
✓ [API /execute] Called - LIVE TRADE
✓ [API /execute] ✓ Zerodha order ACCEPTED - Order ID: 892364102938

Watch Trades:
✓ [API /trades/active] Returning 1 active trades from Zerodha
```

---

## 🚨 Warning Signs (Should NOT See)

❌ `movement_factor = random.uniform(-0.005, 0.01)` 
❌ `base_values = {'NIFTY': 25157.50}` (hardcoded)
❌ `[MarketIntelligence] ✗ Zerodha quote fetch FAILED`
❌ Prices updating after 3:30 PM IST

---

## 🔑 Key Endpoints

| Endpoint | What It Does | Data Source |
|----------|-------------|-------------|
| `GET /autotrade/market/indices` | Get live prices | Zerodha LTP |
| `POST /autotrade/analyze` | Generate signals | Zerodha + analysis |
| `POST /autotrade/execute` | Place real trade | Zerodha order |
| `GET /autotrade/trades/active` | See active trades | Zerodha trades |

---

## 📊 Data Flow

```
Zerodha Account
    ↓
Zerodha Kite API (LTP prices)
    ↓
Market Intelligence (trend analyzer)
    ↓
Auto Trading Engine
    ↓
Your Dashboard (shows REAL data)
```

---

## ✅ Verification Steps

1. **Check Zerodha Connected:**
   ```
   Terminal: [MarketIntelligence] ✓ Zerodha data fetched
   Dashboard: Prices showing live numbers
   ```

2. **Check Prices are Real:**
   ```
   Terminal: [MarketIntelligence] ✓ NSE:NIFTY 50: last_price=25079.90
   Compare: Match with Zerodha app or NSE website
   ```

3. **Check Orders are Real:**
   ```
   Terminal: [API /execute] ✓ Zerodha order ACCEPTED - Order ID: 892364102938
   Zerodha App: Order appears in Orders section
   ```

---

## 🎮 Live Trading Flow

```
You
  ↓
Click "📊 Analyze"
  ↓ [Terminal shows] Zerodha fetching LTP...
Dashboard shows signals with REAL prices
  ↓
Click "▶ Start Auto-Trading"
  ↓ [Terminal shows] Order placed to Zerodha...
Real trade executed in your Zerodha account
  ↓
Watch Live:
- Price updates from Zerodha
- P&L calculated from real prices
- All logged in terminal
```

---

## 💬 How to Read Logs

### ✓ Good Signs

```
✓ = Success
▶ = In progress
⚠ = Warning (but continuing)
✗ = Error/Failed
```

### Log Example

```
[MarketIntelligence] ▶ Fetching LTP for: ['NSE:NIFTY 50', 'NSE:NIFTY BANK']
                    [Getting prices from Zerodha...]
[MarketIntelligence] ✓ NSE:NIFTY 50: last_price=25079.90, volume=18234567
                    [Got NIFTY price: 25,079.90 with volume]
```

---

## 🔍 See Each Call's Performance

Open backend terminal while trading:

1. **Market Fetch Speed:**
   ```
   [MarketIntelligence] ▶ Connecting to Zerodha Kite API...
   [MarketIntelligence] ✓ Zerodha LTP Response received: 850ms
   ```

2. **Signal Generation Speed:**
   ```
   [_live_signals] Generating signals for symbols: ['NIFTY', 'BANKNIFTY']
   [_live_signals] ✓ Generated 2 signals total: 120ms
   ```

3. **Order Placement Speed:**
   ```
   [API /execute] ▶ Placing LIVE order to Zerodha...
   [API /execute] ✓ Zerodha order ACCEPTED: 280ms
   ```

---

## 📈 P&L is Now Real

```
Entry Price (from Zerodha): 940.05
Current Price (from Zerodha): 945.90
P&L = (945.90 - 940.05) × 30 = ₹177

↓ All prices are LIVE from Zerodha ↓

No simulation, no hardcoding, 100% real.
```

---

## 🎯 You Can Trust These Numbers Now

Before: ❌ Simulated
- Prices: Random walk
- Trades: Paper trades
- P&L: Fake updates

Now: ✅ LIVE
- Prices: ✓ Zerodha LTP
- Trades: ✓ Real Zerodha orders
- P&L: ✓ Calculated from real prices

---

## 🚀 Start Trading

```bash
# Terminal 1: Backend
python backend/app/main.py
# Watch logs for: ✓ Zerodha data fetched

# Terminal 2: Frontend
cd frontend && npm run dev
# Open http://localhost:5173

# Dashboard
Click "📊 Analyze" → See LIVE prices
Click "▶ Execute" → See real order in Zerodha
Watch terminal → See every API call
```

---

## ❓ Quick Help

**Prices not updating?**
- Check: `[MarketIntelligence] ✓ Zerodha data fetched`
- If missing: Zerodha not connected (check credentials)

**Order not going through?**
- Check: `[API /execute] ✓ Zerodha order ACCEPTED`
- If shows error: See [DEBUG_LOGGING_GUIDE.md](DEBUG_LOGGING_GUIDE.md)

**Want to see exact Zerodha responses?**
- See: [DEBUG_LOGGING_GUIDE.md](DEBUG_LOGGING_GUIDE.md#step-2-log-trade-execution-details)

---

## 📚 Docs

- `LIVE_DATA_VERIFICATION.md` - Verify it's working
- `DEBUG_LOGGING_GUIDE.md` - Enable detailed logs
- `LIVE_TRADING_COMPLETE.md` - Full explanation
- Terminal output - Real-time performance

---

## ✅ Bottom Line

**Everything you see is LIVE from Zerodha.**
**Every trade is REAL to your account.**
**Every price is REAL from LTP API.**

Happy trading! 🚀
