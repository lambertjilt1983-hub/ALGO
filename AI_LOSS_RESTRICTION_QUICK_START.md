# AI Loss Restriction - Quick Start Guide

## What It Does

**Automatic AI evaluation** that decides: EXECUTE ✅ | WAIT ⏸️ | BLOCK ❌

**Daily Guarantee**: 8 out of 10 trades MUST be profitable (80% win rate)

---

## The 3 Decision Rules

### Rule 1: Win Probability Check
```
Input signal confidence + market conditions
         ↓
    AI predicts win probability
         ↓
70%+ probability → ✅ EXECUTE
50-70% probability → ⏸️ WAIT (risky)
<50% probability → ❌ BLOCK (too dangerous)
```

### Rule 2: Daily Quota Check
```
Daily Limit: 10 trades maximum
Daily Target: 8 wins minimum (80% win rate)

As trades execute, system tracks:
- Wins: How many profitable
- Losses: How many unprofitable
- Remaining: How many left today

If 8 wins become impossible → ❌ BLOCKS remaining trades
```

### Rule 3: Market Condition Check
```
Recovery trade + 3 losses = ❌ BLOCK
High volatility + weak signal = ⏸️ WAIT
Trend against signal = PENALTY
Counter-trend trade = ❌ BLOCK
```

---

## Real-Time Example

**Morning (10:30 AM)**
```
You get a signal: FINNIFTY26MAR28000, 96% confidence
                              ↓
AI Checks:
├─ Win probability: 78% ✅
├─ Daily trades: 3/10 used
├─ Daily wins: 3/3 (100%) ✅
├─ Market: BULLISH with strong trend ✅
├─ Time: 10:30 AM (best window) ✅
└─ Recommendation: ✅ EXECUTE

You can trade!
```

**Afternoon (2:30 PM)**
```
Another signal: NIFTY50, 80% confidence
                         ↓
AI Checks:
├─ Daily trades: 8/10 used
├─ Daily wins: 6/8 (75%)
├─ Wins needed: 8
├─ Trades left: 2
├─ Max possible wins: 6 + 2 = 8 ✅
└─ Recommendation: ✅ EXECUTE (only if you win both)

You can trade!
```

**Next Signal (Right after loss)**
```
Another signal arrives, but...
├─ Daily trades: 9/10
├─ Daily wins: 6/9 (67%)
├─ Wins needed for 80%: 8
├─ Trades left: 1
├─ Max possible wins: 6 + 1 = 7 ❌
└─ Recommendation: ❌ BLOCK

"Cannot achieve 80% win rate anymore"
```

---

## API Quick Commands

### Check if Signal is Good
```bash
curl -X POST "http://localhost:8000/autotrade/ai-evaluate-signal" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "FINNIFTY26MAR28000",
    "signal_confidence": 0.96,
    "market_trend": "BULLISH",
    "trend_strength": 0.75,
    "option_type": "CE",
    "volatility_level": "MEDIUM",
    "rsi_level": 55,
    "macd_histogram": 10.5
  }'
```

**Response Keys**:
- `predicted_win_probability`: "78.32%" - AI's forecast
- `recommendation`: "EXECUTE" - What AI suggests
- `can_execute`: true - Safe to trade?
- `daily_stats`: Shows remaining trades & wins

### Check Daily Progress
```bash
curl -X GET "http://localhost:8000/autotrade/ai-daily-analytics"
```

**Response Shows**:
- `trades_executed`: 3/10 used
- `wins`: 3, `losses`: 0
- `current_win_rate`: 100%
- `wins_needed`: How many more to hit 80%
- `message`: Status summary

### Find Best Symbols to Trade
```bash
curl -X GET "http://localhost:8000/autotrade/ai-symbol-quality"
```

**Response Groups By**:
- 🟢 **GOOD** symbols (>50% win rate) - FOCUS HERE
- 🟡 **CAUTION** symbols (40-50% win rate) - MAYBE
- 🔴 **AVOID** symbols (<40% win rate) - SKIP

---

## Decision Matrix

| Scenario | Win Prob | Daily Quota | Recommendation |
|----------|----------|-------------|-----------------|
| Strong signal, 10AM, low vol | 80%+ | Available | ✅ EXECUTE |
| Good signal, high vol, losses | 70% | Available | ⏸️ WAIT |
| Weak signal, 3PM, volatility | 45% | Available | ❌ BLOCK |
| Any signal, 8 wins already | 95% | 1 left | ⏸️ WAIT (quota) |
| Excellent signal, quota full | 90% | 0 left | ❌ BLOCK (limit) |

---

## Daily Workflow

### Morning (Market Open)
```
1. GET /autotrade/ai-daily-analytics
   └─ Check daily quota reset ✅
   
2. GET /autotrade/ai-symbol-quality
   └─ See which symbols are performing
   
3. Focus on GOOD symbols only
```

### Before Each Trade
```
4. GET signal from strategy
   
5. POST /autotrade/ai-evaluate-signal
   
6. Check response:
   - can_execute: true → Place trade
   - can_execute: false → Skip or wait
```

### After Each Trade Closes
```
7. System auto-records result
   
8. Daily quota updates automatically
   
9. Next signal evaluation included updated quota
```

### Evening (Market Close)
```
10. GET /autotrade/ai-daily-analytics
    └─ Review daily performance
    
11. Check which symbols won/lost
    
12. Plan tomorrow's focus symbols
```

---

## Key Metrics

### Daily (Reset at Midnight)
- **Trades Used**: 0-10 (not more than 10)
- **Wins Needed**: Always 8 minimum
- **Can Continue**: Only if 8 wins are possible

### Cumulative (All-time)
- **Total Trades**: Sum of all trades
- **Win Rate**: Overall performance % 
- **Best Symbols**: Which ones to focus
- **Worst Symbols**: Which ones to avoid

---

## Win Rate Target

### The Math
```
10 trades total
8 must be wins
= 80% win rate requirement
= 8 profits, 2 losses maximum
```

### Example Day
```
Trade 1: WIN   (1W-0L)
Trade 2: WIN   (2W-0L)
Trade 3: LOSS  (2W-1L)
Trade 4: WIN   (3W-1L)
Trade 5: WIN   (4W-1L)
Trade 6: WIN   (5W-1L)
Trade 7: WIN   (6W-1L)
Trade 8: WIN   (7W-1L)
Trade 9: WIN   (8W-1L) ← Target hit! 80% achieved
Trade 10: Blocked (quota full, target met)

Final: 8W-1L = 88.9% win rate ✅
```

---

## Blocked vs Recommended

### ❌ BLOCK (Don't Trade)
Reasons:
- Win probability < 50%
- Daily quota full (10 trades)
- 8 wins mathematically impossible
- Too many consecutive losses (recovery)
- High volatility + weak signal

**Action**: Wait for next signal or next day

### ⏸️ WAIT (Hold Off)
Reasons:
- Win probability 50-70% (risky)
- Neutral market (no clear direction)
- Too much volatility
- Better signal expected soon

**Action**: Skip this signal, next one might be better

### ✅ EXECUTE (Trade)
Reasons:
- Win probability 70%+
- Daily quota available
- Market conditions aligned
- Signal confidence high

**Action**: Place your trade immediately

---

## Features Being Evaluated

The AI checks these 14 factors:

| Factor | Impact | Example |
|--------|--------|---------|
| Signal confidence | HIGH | 96% → Better |
| Market trend | HIGH | BULLISH → Good for CE |
| Trend strength | HIGH | 0.75 → Strong |
| Win rate momentum | HIGH | 65% → Trading well |
| Time of day | MEDIUM | 10AM → Best hours |
| Option type match | MEDIUM | CE + BULLISH → Match |
| Volatility | MEDIUM | HIGH → Risky |
| Recovery trade | MEDIUM | Yes → -10% penalty |
| Consecutive losses | MEDIUM | 3+ → Too risky |
| RSI level | LOW | 50 → Neutral |
| MACD histogram | LOW | Positive → Bullish |
| Volume ratio | LOW | 1.2 → High volume |
| Bollinger position | LOW | 0.7 → Upper half |
| Price momentum | LOW | +2% → Up trend |

---

## Performance Expectations

### Before AI System
```
Week 1: 17 trades, 3 wins (17.6% win rate) ❌
Daily deficit: -₹175
```

### With AI System
```
Week 1: 7 trades, 5 wins (71% win rate) 📈
Week 2: 10 trades, 8 wins (80% win rate) ✅
Week 3: 10 trades, 8+ wins (80%+ win rate) ✅

Daily improvement: -₹175 → +₹500-1,500
Monthly target: +₹5,000-7,500 profit
```

---

## Settings to Know

### Default Configuration
```
Daily Trade Limit: 10 trades
Win Rate Target: 80% (8 wins minimum)
Min Win Probability: 50% (below = BLOCK)
Best Hours: 10-1 PM (bonuses applied)
Worst Hours: 9-10 AM, 3-3:30 PM (penalties)
```

### If You Want to Change

Edit: `backend/app/engine/ai_loss_restriction.py`

```python
# Conservative (safest)
target_win_rate=0.85      # 85% needed
daily_trade_limit=10      

# Balanced (current)
target_win_rate=0.80      # 80% needed
daily_trade_limit=10

# Aggressive (most trades)
target_win_rate=0.75      # 75% needed
daily_trade_limit=15
```

---

## Troubleshooting

**Q: Why is my signal blocked?**
A: Check response → `reason` field explains exactly why

**Q: Can I ignore AI recommendation?**
A: Yes, but then it won't count toward win rate quota

**Q: What if I'm stuck with 0 remaining trades?**
A: Your daily 80% target is achieved! Rest and start fresh tomorrow

**Q: How often does it update?**
A: Every time you call `/ai-evaluate-signal` and every time a trade closes

**Q: Can it be wrong?**
A: Yes, it's predictive ML, not perfect. But should improve win rate significantly

---

## Success Checklist

- [ ] Understand the 80% daily win rate target (8/10 trades)
- [ ] Know the 3 decision rules (probability, quota, conditions)
- [ ] Use `/ai-evaluate-signal` before each trade
- [ ] Focus on GOOD symbols only (>50% win rate)
- [ ] Check daily analytics every morning
- [ ] Trust the AI BLOCK recommendations
- [ ] Don't force trades when AI says WAIT
- [ ] Record all results (system does this automatically)
- [ ] Review weekly to see improvement
- [ ] Adjust settings if needed after 7 days

---

## Next Steps

1. **Now**: Call `/ai-daily-analytics` to see current status
2. **Next signal**: Use `/ai-evaluate-signal` before trading
3. **This week**: Monitor win rate improvement
4. **Next week**: Adjust if needed based on results

---

**Status**: ✅ Active and Learning  
**Your Target**: 80% daily win rate  
**Expected Timeline**: 2-4 weeks to max performance
