# 🤖 Auto Trading Engine - Demo & Live Mode Guide

## 📋 Overview

The Auto Trading Engine now supports **two distinct modes**:

### 🎯 **DEMO Mode** (Default)
- Uses **real live market data** from NSE
- Simulates trade execution
- **No real money** involved
- Perfect for testing strategies
- All P&L is virtual

### ⚡ **LIVE Mode** (Production)
- Uses **real live market data** from NSE
- Executes **actual trades** through broker APIs
- **Real money** at risk
- Requires broker authentication
- All P&L is real

---

## 🎛️ Dashboard Features

### Mode Toggle
- **Blue Badge** 🎯 = DEMO Mode
- **Red Badge** ⚡ = LIVE Mode
- Click "Switch to LIVE/DEMO" button to change modes
- Safety confirmation when switching to LIVE

### Real-Time Data Display
- **Live NIFTY Price** updates every 10 seconds
- **Trading Signals** with confidence levels
- **Active Trades** monitoring
- **P&L Tracking** (Demo or Real)

### Trade Execution
- **Demo Mode**: Shows "🎯 DEMO: Trade executed"
- **Live Mode**: Shows "⚡ LIVE TRADE EXECUTED"
- Double confirmation for live trades

---

## 🔧 How It Works

### Market Data Flow
```
NSE API → Auto Trading Engine → Strategy Analysis → Signal Generation
```

### Demo Mode Flow
```
1. Fetch live NIFTY/BANKNIFTY price from NSE
2. Analyze using 4 strategies (RSI+MACD, Bollinger, Trend, S/R)
3. Generate high-confidence signals (>70%)
4. SIMULATE trade execution
5. Track virtual P&L
```

### Live Mode Flow
```
1. Fetch live NIFTY/BANKNIFTY price from NSE
2. Analyze using 4 strategies
3. Generate high-confidence signals (>70%)
4. EXECUTE REAL trade via broker API
5. Track actual P&L
6. Monitor stop-loss and target
```

---

## 📊 API Endpoints

### Switch Mode
```
POST /autotrade/mode?demo_mode=true|false
```

**Demo Mode:**
```json
{
  "success": true,
  "is_demo_mode": true,
  "mode": "DEMO",
  "message": "Switched to DEMO mode. Trades will be simulated only."
}
```

**Live Mode:**
```json
{
  "success": true,
  "is_demo_mode": false,
  "mode": "LIVE",
  "message": "Switched to LIVE mode. ⚠️ REAL trades will be executed!"
}
```

### Analyze Market
```
POST /autotrade/analyze?symbol=NIFTY&balance=100000
```

**Response:**
```json
{
  "success": true,
  "live_price": 22450.75,
  "is_demo_mode": true,
  "signals": [...],
  "recommendation": {
    "action": "BUY",
    "symbol": "NIFTY",
    "confidence": 89.1,
    "entry_price": 22450.75,
    "stop_loss": 22001.74,
    "target": 23123.77,
    "quantity": 2
  }
}
```

### Execute Trade
```
POST /autotrade/execute?symbol=NIFTY&balance=100000&broker_id=1
```

**Demo Response:**
```json
{
  "success": true,
  "is_demo_mode": true,
  "message": "✓ DEMO: BUY 2 NIFTY @ ₹22450.75",
  "trade": {...}
}
```

**Live Response:**
```json
{
  "success": true,
  "is_demo_mode": false,
  "message": "⚡ LIVE TRADE EXECUTED: BUY 2 NIFTY @ ₹22450.75",
  "trade": {...}
}
```

---

## 🛡️ Safety Features

### Demo Mode Protection
✅ Default mode is DEMO  
✅ No real money at risk  
✅ Perfect for learning  
✅ Can test unlimited strategies  

### Live Mode Protection
⚠️ Double confirmation required  
⚠️ Clear warning messages  
⚠️ Requires broker authentication  
⚠️ Stop-loss auto-enabled  
⚠️ Max daily loss limit (5%)  
⚠️ Position size limits (60% max)  

---

## 📈 Trading Statistics

Both modes track:
- Total trades executed
- Win rate percentage
- Daily P&L (₹)
- Active trades count
- Winning vs Losing trades

**Demo Mode Stats:**
- Virtual P&L
- Learning metrics
- Strategy testing results

**Live Mode Stats:**
- Real P&L
- Actual broker executions
- Real money performance

---

## 🚀 Usage Guide

### Testing New Strategies (Demo Mode)

1. **Enable Demo Mode** (default)
   - Dashboard shows 🎯 DEMO badge
   
2. **Click "Analyze"**
   - Fetches live NIFTY price
   - Shows all strategy signals
   - Displays recommendation
   
3. **Enable Auto Trading**
   - Click "▶ Enable" button
   
4. **Execute Trade**
   - System auto-executes on signals
   - Or manually click trade button
   
5. **Monitor Results**
   - View active trades
   - Check P&L (virtual)
   - Review trade history

### Live Trading (Production)

1. **⚠️ IMPORTANT: Test in Demo First!**
   
2. **Connect Broker Account**
   - Add broker credentials
   - Complete OAuth authentication
   
3. **Switch to LIVE Mode**
   - Click "⚡ Switch to LIVE"
   - Confirm warning popup
   - Dashboard shows ⚡ LIVE badge
   
4. **Enable Auto Trading**
   - Click "▶ Enable"
   - System monitors market
   
5. **Auto Execution**
   - Trades execute automatically
   - Real money at risk
   - Stop-loss protection active
   
6. **Monitor Closely**
   - Watch active trades
   - Check real P&L
   - Ensure stop-loss working

---

## 🎯 Market Data Sources

### Live Price Fetching

**Primary Source:** NSE India API
```javascript
URL: https://www.nseindia.com/api/option-chain-indices
Symbols: NIFTY, BANKNIFTY
Update: Every 10 seconds
```

**Data Points:**
- Underlying value (spot price)
- Option chain data
- Volume and OI
- Implied volatility

**Fallback:** Simulated realistic pricing
- Based on time-of-day patterns
- Historical volatility
- Deterministic for consistency

---

## 🔔 Important Notes

### Demo Mode
✅ **Use for:**
- Learning how auto-trading works
- Testing new strategies
- Practicing risk management
- Building confidence
- Backtesting ideas

❌ **Limitations:**
- No real P&L
- Can't test broker execution speed
- Market impact not simulated
- Slippage not included

### Live Mode
✅ **Best for:**
- Proven strategies
- Real trading experience
- Actual profit generation
- Professional trading

⚠️ **Risks:**
- Real money loss possible
- Broker fees apply
- Market volatility
- Execution delays
- System failures

---

## 📞 Support

**Issues with Demo Mode:**
- Check browser console for errors
- Verify market hours (9:15 AM - 3:30 PM IST)
- Refresh page if data not updating

**Issues with Live Mode:**
- Verify broker authentication
- Check broker balance
- Ensure market is open
- Contact broker support if needed

---

## 🎓 Best Practices

1. **Always Start with Demo**
   - Test for at least 1 week
   - Verify win rate >50%
   - Check risk management

2. **Small Positions in Live**
   - Start with 1-2 trades max
   - Use minimum quantity
   - Monitor closely

3. **Set Alerts**
   - Daily loss limits
   - Position size limits
   - Trade count limits

4. **Regular Review**
   - Daily P&L analysis
   - Strategy performance
   - Adjust parameters

---

**Last Updated:** January 22, 2026  
**Status:** ✅ Production Ready  
**Dashboard:** http://localhost:3000  
**API Docs:** http://localhost:8002/docs
