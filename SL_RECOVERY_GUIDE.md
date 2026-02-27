# SL Recovery Strategy - Implementation Guide

## Overview

The SL Recovery Manager is an intelligent trading enhancement that implements a smarter approach to handling stop loss hits. Instead of immediately placing the same trade again after a loss, it:

1. **Waits 5 minutes** after a stop loss hit to allow the market to stabilize
2. **Requires high-confidence signals (>95%)** before considering re-entry
3. **Avoids the same option symbol** that just hit the stop loss
4. **Switches to the opposite option type** (CE→PE or PE→CE) for better probability
5. **Analyzes market trend** before authorizing recovery trades

## Key Features

### 1. 5-Minute Wait Period
After a stop loss hit on a symbol, the system prevents any trades on that base symbol for 5 minutes.

**Benefit**: Avoids emotional trading and whipsaw losses. Allows the market to establish a new direction.

**Example Timeline**:
- 08:27:44 AM: SL hit on `FINNIFTY26MAR28000CE`
- 08:27:44 - 08:32:44 AM: **Wait Period** (5 minutes) - No trades allowed
- 08:32:44 AM+: Can retry with high-confidence signal on alternative option type (PE)

### 2. >95% Confidence Requirement
Recovery signals must have a confidence level above 95% to be approved for execution.

**Why 95%?**
- Your recent trades show lots of losses with lower-confidence signals
- 95% confidence ensures only the strongest signals are traded
- Filters out mediocre setups that increase risk

**Confidence Sources**:
- Multiple confirming technical indicators (RSI + MACD)
- Strong trend alignment (Bollinger Bands, Moving Averages)
- Market structure support/resistance breaks
- Volume confirmation

### 3. Alternative Option Type Selection
If CE hit a stop loss, recommend PE (and vice versa) on the same base symbol.

**Example**:
```
❌ Lost: FINNIFTY26MAR28000CE (SL hit)
✅ Retry: FINNIFTY26MAR28000PE (opposite type, same strike)
```

**Why?** 
- CE approaching support → bears control → try PE (downside play)
- PE approaching resistance → bulls control → try CE (upside play)
- Switches trading direction to adapt to market tone

### 4. Avoid Same Symbol Trades
The system prevents re-entry on the exact same symbol immediately after a loss.

**Protection**:
- Prevents mechanical revenge trading
- Forces consideration of different strike/expiry
- Encourages trading options with better technical setups

### 5. Market Trend Analysis
Before approving recovery trades, the system analyzes:

**Trend Determination**:
- **BULLISH** (>60% up moves): Better for CE trades
- **BEARISH** (<40% up moves): Better for PE trades  
- **NEUTRAL**: More caution required

**Trend Strength** (0.0 to 1.0):
- >0.8 = Strong trend (safer recovery entry)
- 0.5-0.8 = Moderate (needs additional confirmation)
- <0.5 = Weak (avoid trading)

## Trade Entry Status Tracking

### Trade States
```
OPEN          → Active trade
├─ TARGET_HIT → Closed at target (profit)
├─ SL_HIT     → Closed at stop loss (loss) ← RECOVERY TRIGGERED
├─ EXPIRED    → Options expired
└─ AUTO_CLOSE_3_29PM → Closed before market end
```

When a trade closes with `SL_HIT` status:
1. Details are logged to `sl_recovery_manager.sl_hit_history`
2. 5-minute countdown starts
3. Recovery signal APIs become available

## API Endpoints

### 1. Check Recovery Status
```
GET /autotrade/recovery-status
```

**Response**:
```json
{
  "success": true,
  "total_sl_hits": 14,
  "symbols_with_sl": ["FINNIFTY26MAR28000", "NIFTY2630225300", ...],
  "symbols_needing_recovery": [
    {
      "symbol": "FINNIFTY26MAR28000",
      "reason": "Waiting 2.3 min after SL hit (required 5 min)",
      "retry_count": 1
    }
  ],
  "wait_minutes": 5,
  "min_confidence": "95.00%",
  "max_retries_per_day": 3,
  "retry_attempts_today": {
    "FINNIFTY26MAR28000": 1,
    "NIFTY2630225300": 2
  }
}
```

**Use Cases**:
- Check if a symbol is still in wait period
- See how many retries remaining for today
- Understand why certain symbols can't be traded

### 2. Generate Recovery Signal
```
POST /autotrade/recovery-signal

{
  "base_symbol": "FINNIFTY26MAR28000",
  "signal_confidence": 0.97,
  "current_price": 510.50,
  "recent_prices": [508.0, 509.5, 510.0, 510.5]
}
```

**Response**:
```json
{
  "success": true,
  "symbol": "FINNIFTY26MAR28000",
  "option_type": "PE",
  "recommendation": "BUY",
  "confidence": "97.00%",
  "market_trend": "BEARISH",
  "trend_strength": "0.75",
  "reason": "Recovery signal: BEARISH market, confidence 97.00%, trend strength 0.75",
  "should_execute": true,
  "execution_reason": "All checks passed",
  "can_trade": true,
  "min_confidence_required": "95.00%"
}
```

**Signal Interpretations**:

| Recommendation | Action | When |
|---|---|---|
| `BUY` | Execute recovery trade | All checks pass, confidence >95%, aligned trend |
| `WAIT` | Do not trade yet | Below confidence, wait period active, weak trend |
| Recommendation = `BUY` + `should_execute` = `true` | **GREEN LIGHT** ✅ | Safe to place trade |
| Recommendation = `WAIT` OR `should_execute` = `false` | **RED LIGHT** ❌ | Skip recovery for now |

## Configuration

### Default Settings
```python
# sl_recovery_manager = SLRecoveryManager(
#     wait_minutes=5,              # Wait 5 min after SL hit
#     min_confidence=0.95          # >95% confidence required
# )
```

### Daily Limits
```python
max_retries_per_day = 3  # Max 3 retries per base symbol per day
```

After hitting max retries, no more recovery trades allowed for that symbol that day.

## Real Example from Your Trade History

### Trade #2: SL Hit Recovery Opportunity
```
#2: FINNIFTY26MAR28000CE
Entry:   ₹509.45 at 07:47:44 AM
Exit:    ₹484.45 at 07:47:44 AM (SL_HIT)
Loss:    ₹-1,500

Recovery Window Opens: 07:47:44 AM + 5 min = 07:52:44 AM
```

**What the system would do**:
1. **07:47:44**: Record SL hit for `FINNIFTY26MAR28000` + `CE` type
2. **07:47:44 - 07:52:44**: **WAIT** - No trades allowed
3. **07:52:44+**: If high-confidence signal appears:
   - ✅ Suggest `FINNIFTY26MAR28000PE` (flip to PE)
   - ✅ Check if market is trending down (BEARISH)
   - ✅ If confidence >95% + BEARISH trend → **Approve recovery trade**
   - ❌ If confidence <95% or market unclear → **Block recovery**

## Integration with Signal Generation

The SL Recovery Manager works alongside your existing signal generation:

```
Signal Generator
    ↓
Confidence Score
    ↓
    ├─ >95%? → Yes ↓
    │  SL Recovery Manager
    │     ├─ Wait period active? → Check
    │     ├─ Same symbol? → Avoid
    │     ├─ Market trend? → Analyze
    │     ├─ Retry limit? → Enforce
    │     └─ Approval? → YES ✅ or NO ❌
    │
    └─ ≤95%? → WAIT for better signal
```

## Benefits for Your Trading

### Before (Current Situation)
- Win rate: 3/17 = **17.6%** ❌
- Range P&L: **₹-4,724.5** ❌
- Many SL hits followed by repeat entries immediately

### After (With SL Recovery)
- **Fewer trades**: Only trade when ready (5-min wait + 95% confidence)
- **Better selectivity**: Second chances only for strongest signals
- **Trend-aligned**: CE/PE swaps match market direction
- **Reduced whipsaw**: 5-minute buffer prevents revenge trading

**Expected Improvement**:
- Win rate target: **40-50%** (with fewer, higher-quality trades)
- Profit per trade: More consistent
- Daily P&L: Better managed through quality over quantity

## Best Practices

### ✅ DO
1. **Check recovery status** before placing manual trades
2. **Use the 95% threshold** - don't lower it
3. **Honor the 5-minute wait** - don't try to beat the timer
4. **Respect market trends** - don't trade against them
5. **Track daily limit** - max 3 retries per symbol per day

### ❌ DON'T
1. **Don't trade same symbol immediately** after SL hit
2. **Don't ignore confidence threshold** even if you think it's good
3. **Don't force recovery trades** against market trend
4. **Don't exceed daily retry limit** for a symbol
5. **Don't trade during weak trends** without strong signal

## Example Recovery Scenarios

### Scenario 1: ✅ Approved Recovery
```
SL Hit: FINNIFTY26MAR28000CE @ 07:47 AM
├─ Wait 5 min? ✅ (07:52 AM reached)
├─ Confidence >95%? ✅ (96% signal appears)
├─ Market BEARISH? ✅ (75% down moves)
├─ Option flip CE→PE? ✅ (Recommended)
└─ Decision: APPROVE RECOVERY ✅

→ Place: FINNIFTY26MAR28000PE
```

### Scenario 2: ❌ Wait for Better Signal
```
SL Hit: NIFTY2630225300CE @ 06:53 AM  
├─ Wait 5 min? ✅ (Already passed)
├─ Confidence >95%? ❌ (83% signal - TOO LOW)
├─ Market trend? ⚠️ (Neutral)
└─ Decision: WAIT FOR BETTER SIGNAL ❌

→ Skip trade, wait for 95%+ confidence
```

### Scenario 3: ❌ Daily Limit Exceeded
```
SL Hit: BANKNIFTY26MAR60800CE @ 05:48 AM
├─ Wait 5 min? ✅ (Passed)
├─ Confidence >95%? ✅ (97% appears)
├─ Retry count today? ❌ (Already 3 retries - MAX HIT)
└─ Decision: DAILY LIMIT REACHED ❌

→ No more retries for BANKNIFTY60800 today
```

## Monitoring Your Recovery Trades

### Track in database:
```
PaperTrade table:
- status: 'SL_HIT' → Initial stop loss
- signal_data: Contains recovery details
- entry_time, exit_time: Show wait period
```

### Check logs:
```
Look for: [SL_RECOVERY] messages
- "Recorded SL hit"
- "Cannot retry" (shows reason)
- "Recovery signal"
- "All checks passed"
```

## Support & Troubleshooting

### Issue: Trading is paused after SL hits
**Solution**: Check recovery-status endpoint to see wait period remaining

### Issue: Want to force a recovery trade
**Solution**: If confidence >95% and trends align, use recovery-signal endpoint to approve

### Issue: Same symbol hit SL multiple times
**Solution**: System limits to 3 retries/day - exceeding this prevents further trades to protect capital

### Issue: Want to change wait time or confidence
**Change in code**:
```python
# backend/app/engine/sl_recovery_manager.py
sl_recovery_manager = SLRecoveryManager(
    wait_minutes=5,      # ← Change wait time here
    min_confidence=0.95  # ← Change confidence threshold here
)
```

## Summary

The SL Recovery Manager transforms your trading by:

1. **Preventing panic trades** (5-min wait)
2. **Filtering mediocre signals** (95% confidence)
3. **Adapting to market tone** (CE/PE swaps)
4. **Protecting capital** (Daily retry limits)
5. **Improving win rate** (Quality over quantity)

This should help you achieve **40-50% win rate** with **positive daily P&L** by trading only the strongest signals at the right moments.

---

**Implementation Status**: ✅ Complete
**Last Updated**: February 27, 2026
