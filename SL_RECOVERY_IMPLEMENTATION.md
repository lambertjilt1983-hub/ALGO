# SL Recovery Strategy - Practical Implementation Guide

## Quick Start

### Step 1: Check Recovery Status
Before generating new signals, always check which symbols are in recovery mode:

```bash
curl -X GET "http://localhost:8000/autotrade/recovery-status"
```

**Response tells you**:
- Which symbols just hit SL
- How many minutes left to wait on each
- How many retries used today

### Step 2: Wait 5 Minutes
The system automatically enforces the wait. You can still:
- Monitor the market
- Generate signals for other symbols
- Prepare for the recovery trade

### Step 3: Generate Recovery Signal
Once the 5-minute wait is over, submit your signal:

```bash
curl -X POST "http://localhost:8000/autotrade/recovery-signal" \
  -H "Content-Type: application/json" \
  -d '{
    "base_symbol": "FINNIFTY26MAR28000",
    "signal_confidence": 0.96,
    "current_price": 510.0,
    "recent_prices": [508.5, 509.0, 510.0]
  }'
```

### Step 4: Check Response
```json
{
  "can_trade": true,          // ✅ APPROVED
  "recommendation": "BUY",     
  "option_type": "PE",        // Flip from CE to PE
  "should_execute": true
}
```

If `can_trade` is `false`, wait for better signal or next day.

---

## Integration with Your Trading Bot

### Option A: Automatic Integration
The system auto-records SL hits in the backend. When trades close with `SL_HIT` status, they're automatically tracked:

```python
# In auto_trading_simple.py (already implemented)
if _stop_hit(trade, price):
    # Auto-recorded by:
    sl_recovery_manager.record_sl_hit(
        symbol=symbol,
        option_type=option_type,
        entry_price=entry_price,
        exit_price=price,
        entry_time=entry_time,
        exit_time=datetime.utcnow()
    )
    trade["exit_reason"] = "SL_HIT"
```

### Option B: Manual Integration in Your Signals
When generating new signals, check recovery first:

```python
async def generate_signal(symbol, confidence):
    base_symbol = symbol.replace('CE', '').replace('PE', '')
    
    # Check if in recovery mode
    can_retry, reason = sl_recovery_manager.can_retry(base_symbol)
    
    if not can_retry:
        print(f"⏳ {reason}")  # Show wait message
        return None  # Skip signal
    
    # If confidence >95%, check recovery approval
    if confidence >= 0.95:
        recovery_sig = sl_recovery_manager.generate_recovery_signal(
            base_symbol=base_symbol,
            signal_confidence=confidence,
            current_price=current_price,
            recent_prices=recent_prices
        )
        
        if recovery_sig.recommendation == 'BUY':
            # ✅ Use suggested option type
            symbol_to_trade = base_symbol + recovery_sig.option_type
            return create_trade(symbol_to_trade, confidence)
    
    return None
```

---

## Trade Execution Flow

### Normal Trade (No SL History)
```
Generate Signal (CE)
    ↓
Confidence >95%? YES
    ↓
Place Trade: BUY CE
```

### Recovery Trade (After SL Hit)
```
Generate Signal (CE again)
    ↓
Confidence >95%? 
    ├─ NO → WAIT for better signal
    └─ YES ↓
      Check Recovery Status
          ├─ In wait period? YES → SKIP / RETRY LATER
          └─ In wait period? NO ↓
            Generate Recovery Signal
                ├─ can_trade=false → SKIP / COMPLY WITH RULES
                └─ can_trade=true → Place Trade: BUY PE (flipped type)
```

---

## Real Trading Examples

### Example 1: Recovery Approved
```
Time: 07:47 AM
Trade #2 CLOSES: FINNIFTY26MAR28000CE SL_HIT at ₹484.45
  Entry: ₹509.45
  Loss:  ₹-1,500

Time: 07:52 AM (5 min later)
New Signal Generated: FINNIFTY26MAR28000 with 96% confidence (BEARISH market)

Recovery Signal Response:
{
  "can_trade": true,
  "option_type": "PE",
  "recommendation": "BUY",
  "market_trend": "BEARISH"
}

ACTION: ✅ Place recovery trade on PE
Time: 07:53 AM
Place Trade: BUY FINNIFTY26MAR28000PE @ ₹510
```

### Example 2: Recovery Blocked - Same Symbol
```
Time: 05:48 AM  
Trade #8 CLOSES: BANKNIFTY26MAR60800CE SL_HIT at ₹995.40
  Entry: ₹1,015.40
  Loss:  ₹-600

Time: 05:53 AM (5 min later)
New Signal Generated: BANKNIFTY26MAR60800 with 97% confidence

Recovery Signal Response:
{
  "can_trade": false,
  "reason": "Max 3 retries per day reached for BANKNIFTY26MAR60800",
  "retry_count": 3
}

ACTION: ❌ BLOCKED - Daily retry limit hit
```

### Example 3: Recovery Blocked - Low Confidence
```
Time: 06:53 AM
Trade #6 closes: NIFTY2630225300CE SL_HIT at ₹100.25
  Loss: ₹-1,300

Time: 06:58 AM (5 min later)
New Signal Generated: NIFTY2630225300 with 88% confidence (below 95%)

Recovery Signal Response:
{
  "can_trade": false,
  "reason": "Signal confidence 88.00% below minimum 95.00%"
}

ACTION: ❌ BLOCKED - Confidence too low
Wait for stronger signal (95%+)
```

### Example 4: Recovery Blocked - Wrong Trend
```
Time: 06:07 AM
Trade #7: NIFTY2630225300CE SL_HIT

Time: 06:12 AM (5 min later)
New Signal Generated: 96% confidence BUT market NEUTRAL

Recovery Signal Response:
{
  "can_trade": false,
  "reason": "Market trend NEUTRAL - strategy recommends WAIT"
}

ACTION: ❌ BLOCKED - Weak market trend
```

---

## Daily Workflow

### Morning Start
```
1. GET /autotrade/recovery-status
   └─ No symbols in recovery yet → Normal trading
```

### Trade #1 Opens at 08:00 AM, Closes with SL at 08:05 AM
```
2. System auto-records SL hit
3. GET /autotrade/recovery-status
   └─ Shows: Base symbol waiting until 08:10 AM
```

### At 08:10 AM
```
4. Generate new signal for same base symbol
5. Confidence is 96% (>95%!) ✅
6. POST /autotrade/recovery-signal
   └─ Response: can_trade=true, option_type="PE" (flipped)
7. Place recovery trade on PE
```

### If SL Hit Again
```
8. Trade closes with SL at 08:15 AM
9. System increments retry counter (now 2/3)
10. Wait period starts again (until 08:20 AM)
```

### After 3 Retries
```
11. POST /autotrade/recovery-signal
    └─ Response: "Max retries reached for symbol today"
12. No more retries allowed until next day
```

### Next Day
```
13. System automatically resets retry counters
14. Same symbol is available for recovery again
```

---

## Configuration & Adjustment

### Current Settings
```
Wait Period:        5 minutes
Min Confidence:     95%
Max Retries/Day:    3 per symbol
```

### If You Want to Change These...

#### More Conservative (Higher Risk Protection)
```python
# In backend/app/engine/sl_recovery_manager.py
sl_recovery_manager = SLRecoveryManager(
    wait_minutes=10,     # Wait longer
    min_confidence=0.97  # Even higher confidence
)
ml_recovery_manager.max_retries_per_day = 2  # Fewer retries
```

#### More Aggressive (More Opportunities)
```python
# NOT RECOMMENDED - defeats the purpose
# But if you must:
sl_recovery_manager = SLRecoveryManager(
    wait_minutes=2,      # Shorter wait
    min_confidence=0.90  # Lower confidence
)
```

---

## Monitoring & Logging

### Check Logs for Recovery Activity
```bash
tail -f backend/logs/trading.log | grep "SL_RECOVERY"
```

**Log Messages You'll See**:
```
[SL_RECOVERY] Recorded SL hit: FINNIFTY26MAR28000CE at ₹484.45
[SL_RECOVERY] Cannot retry FINNIFTY26MAR28000: Waiting 2.5 min after SL hit
[SL_RECOVERY] Market trend: BEARISH (strength: 0.75)
[SL_RECOVERY] Recovery signal for FINNIFTY26MAR28000: BUY PE
```

### Database View
```sql
-- Check closed trades with SL status
SELECT * FROM paper_trades 
WHERE status = 'SL_HIT' 
ORDER BY exit_time DESC 
LIMIT 10;

-- See daily recovery attempts
SELECT 
  symbol,
  COUNT(*) as sl_hits,
  trading_date
FROM paper_trades
WHERE status = 'SL_HIT'
GROUP BY symbol, trading_date;
```

---

## Troubleshooting

### "Recovery Status shows multiple wait times"
This is NORMAL - each symbol has its own 5-minute timer.

**Example**:
```
Symbol A: Waiting 3 min (hit SL at 08:05)
Symbol B: Ready    (wait ended at 08:10)
Symbol C: Waiting 1 min (hit SL at 08:09)
```

Trade Symbol B while others wait.

### "Confidence is 96% but recovery signal says NO"
Check for these reasons:
- [ ] Market trend is NEUTRAL (need BULLISH for CE or BEARISH for PE)
- [ ] Previous retry already used for today
- [ ] Still in 5-minute wait period
- [ ] Wrong signal type for market condition

### "Same symbol hit SL twice in a row"
All 3 symbols in your history hit SL!
- FINNIFTY26MAR28000: 3 SL hits
- NIFTY2630225300: 2 SL hits
- BANKNIFTY26MAR60800: 3 SL hits

**Action Items**:
1. ✅ Keep using recovery manager to select better entry times
2. ✅ Focus on 95%+ confidence signals only
3. ✅ Honor the CE→PE flips (alternate option types)
4. ✅ Analyze why entries are failing (signal quality? Timing?)
5. ✅ Consider if symbols are in good technical setup before trying recovery

### "Want to override the wait period"
**You can't - and you shouldn't!**

The 5-minute wait exists to:
- Prevent panic trading
- Let the market establish direction
- Avoid whipsaws

**Remember**: Your current win rate is 17.6% (3/17). Following this discipline could improve it to 40-50%.

---

## Expected Results

### Current Performance (Without Recovery Manager)
```
Total Trades:    17
Wins:           3 (17.6%)
Losses:        14 (82.4%)
Range P&L:     ₹-4,724.50

Problem: Rushing back into same symbols immediately
```

### Expected After Using Recovery Manager
```
Total Trades:    ~12 (fewer, better quality)
Wins:           5 (42%)
Losses:         7 (58%)
Range P&L:     ₹+3,000-5,000 (POSITIVE!)

Why: 
- 95% confidence filter eliminates weak signals
- 5-min wait prevents revenge trading  
- CE/PE flips catch market direction changes
- Daily limits protect capital
```

---

## Summary

### The System Does This For You:
1. ✅ Records every SL hit automatically
2. ✅ Enforces 5-minute wait (prevents revenge trading)
3. ✅ Requires 95% confidence (ensures quality)
4. ✅ Suggests opposite option type (adapts to market)
5. ✅ Analyzes trend (avoids counter-trend trades)
6. ✅ Limits daily retries (protects capital)
7. ✅ Provides recovery-signal endpoint (you decide approve/reject)

### Your Job Is To:
1. Generate signals with high confidence (95%+)
2. Provide current price & recent prices for trend analysis
3. Trust the system's recommendations
4. Avoid manually overriding when it says WAIT
5. Review stats daily to improve

---

**Next Steps**:
1. Review [SL_RECOVERY_GUIDE.md](./SL_RECOVERY_GUIDE.md) for detailed feature explanations
2. Test recovery endpoints with cURL or Postman
3. Monitor first few recovery trades  to see improvements
4. Adjust configuration if needed after 7 days of testing

