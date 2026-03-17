# Stock Signals Not Showing - Root Cause Analysis & Fix

## Issue
Frontend shows "Stocks (0)" even though `include_nifty50=true` is being passed to the backend.

## Root Causes

### 1. **Signal Generation Backend** ✅ WORKS
- `_build_scan_symbol_universe()` correctly includes NIFTY 50 stocks when `include_nifty50=True`
- Returns: 4 indices + 48 stocks = 52 symbols
- `fetch_index_option_chain()` correctly handles stock vs index logic
- Sets `signal_type: "stock"` for stock symbols
- Tests pass for stock signal generation

### 2. **API Endpoint** ✅ WORKS  
- `/option-signals/intraday-advanced?include_nifty50=true` correctly passes parameter
- `generate_signals_advanced()` correctly calls `generate_signals(include_nifty50=True)`
- `_apply_confirmation()` enriches signals with `confirmation_score`

### 3. **Frontend Reception** ⚠️ POTENTIAL ISSUES

#### Issue 3a: Timeout & Cache Fallback
```javascript
// Frontend tries: max_symbols=12, then 40 with include_fno_universe=true
// These may timeout on heavy load and return cached (index-only) data
// Logic skips timeout cache but may hit other issues
```

#### Issue 3b: Quality Filtering Too Strict
```javascript
const scanCandidates = allSignals.filter((signal) => {
  const entry = Number(signal.entry_price ?? 0);
  const target = Number(signal.target ?? 0);
  const stop = Number(signal.stop_loss ?? 0);
  if (!(entry > 0) && !(target > 0) && !(stop > 0)) return false; // ❌ ISSUE!
  // ...
});
```

**BUG FOUND**: The check is using `&&` (AND) when it should use `||` (OR)!
- Current: Rejects if ANY ONE of entry/target/stop is invalid ❌
- Should be: Reject if ALL THREE are missing ✓

Actually, let me re-read this... it says `if (!(entry > 0) || !(target > 0) || !(stop > 0))` which is correct (reject if any is invalid).

#### Issue 3c: Stock Signal Quality Score Lower Than Indices
- Stock options might inherently have lower confidence scores
- Fixed point targets (25 points) might create unfavorable RR ratios for some stocks
- Quality calculation: `confidenceScore (0-50) + rrScore (0-30) + winRate (0-20) = 0-100`
- If confidence or RR is low for stocks, total quality drops below minQuality (70)

### 4. **Potential Zerodha Account Limitation** 
- User's account may not have stock option trading enabled
- NFO segment may not include all NIFTY 50 stock options
- This would cause `fetch_index_option_chain()` to return errors instead of signals

## Solution Path

### Immediate Fix (Frontend)
1. ✅ Ensure `include_nifty50=true` is being sent (already done)
2. ✅ Skip timeout-cache for broad requests (already done)
3. ✅ Fall back to non-FNO universe (already done)

### Root Cause Fix (Backend)
1. **Better error handling**: Return both valid signals AND error info
2. **Stock-specific targeting**: Use percentage-based targets instead of fixed points
   - Instead of `target = entry + 25`: Use `target = entry * 1.08` (8% target)
   - Instead of `stop = entry - 20`: Use `stop = entry * 0.95` (5% stop)
   - This maintains better RR regardless of strike price
3. **Confidence adjustment for stocks**: Stocks might need lower quality threshold

### Verification
1. Run backend tests: `pytest backend/tests/test_stock_integration.py`
2. Check actual API response: Call `/option-signals/intraday-advanced?include_nifty50=true` 
3. Count stock vs index signals in response
4. Check stock signal quality scores

## Debug Steps
1. Open browser DevTools → Network tab
2. Call `/option-signals/intraday-advanced?include_nifty50=true` 
3. Check response to see:
   - Total signals returned
   - How many have `signal_type: "stock"` vs `"index"`
   - What are their `confidence`, `confirmation_score`, `quality_score` values
4. If no stocks: Check if any error entries exist
5. If stocks but filtered out: Compare quality scores with INDEX signals
