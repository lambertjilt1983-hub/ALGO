# Stock vs Index Signal Generation Analysis

## Executive Summary

The system **has infrastructure to generate stock signals**, but stocks may not appear in results due to:

1. **Timeout/caching issues** - Broad scans timeout and return cached index-only results
2. **Default configuration** - By default, only 4 indices are scanned (BANKNIFTY, NIFTY, SENSEX, FINNIFTY)
3. **Filtering stages** - Multiple filtering stages can remove stocks with lower quality scores
4. **Frontend filtering** - Additional client-side filtering removes signals below thresholds

---

## Files Related to Signal Generation

### Backend Signal Generation (`backend/app/engine/option_signal_generator.py`)
**Key Functions:**
- `generate_signals()` - Main entry point (lines 778-900)
- `generate_signals_advanced()` - Enhanced async version (lines 1123+)
- `fetch_index_option_chain()` - Core signal fetcher for both stocks and indices (lines 470+)
- `_build_scan_symbol_universe()` - Determines which symbols to scan (lines 748-775)
- `select_best_signal()` - Filters and ranks signals (lines 916-1020)
- `_validate_signal_quality()` - Quality scoring logic (lines 118-315)

### Frontend Signal Display (`frontend/src/components/AutoTradingDashboard.jsx`)
**Key Functions:**
- `getSignalGroup()` - Classifies signals as 'stocks' or 'indices' (lines 592-604)
- `scanMarketForQualityTrades()` - Market scanning and filtering (lines 807+)
- Signal filtering pipeline with multiple stages (quality, confidence, RR)

### Tests (`backend/tests/test_stock_option_signals.py`)
- Comprehensive test suite for stock signal generation
- Documents expected behavior for stock vs index signals

---

## Stock Signal Generation: How It Works

### 1. Symbol Universe Building (`_build_scan_symbol_universe`)

**Location:** [option_signal_generator.py](backend/app/engine/option_signal_generator.py#L748)

```python
def _build_scan_symbol_universe(
    include_nifty50: bool,
    include_fno_universe: bool,
    max_symbols: int,
    instruments_nfo: List[Dict],
) -> List[str]:
```

**Logic:**
- Always includes 4 indices: `["BANKNIFTY", "NIFTY", "SENSEX", "FINNIFTY"]`
- If `include_nifty50=True`: adds up to `max_symbols` from `NIFTY_50_SYMBOLS` list (lines 30-45)
- If `include_fno_universe=True`: adds additional F&O stocks
- Total stock budget is capped at `max_symbols` (line 751)

**Key Issues:**
- **Default behavior** (`include_nifty50=False`): NO stocks are scanned
- **Max symbols** limits how many stocks can be included
- **Rate limiting** (line 816-818): returns error signals if called too frequently

### 2. Signal Generation Flow

**Location:** [generate_signals()](backend/app/engine/option_signal_generator.py#L778)

```
1. Check rate limiting cache
2. Load Zerodha credentials
3. Fetch instruments (NFO for stocks/indices, BFO for SENSEX)
4. Build symbol universe based on include_nifty50 and include_fno_universe flags
5. For each symbol:
   - Call fetch_index_option_chain()
   - Get spot price, option chain data
   - Calculate quality score
   - Return CE and PE signals
6. Cache results for 60 seconds
```

**Stock Symbol Handling:**

**Location:** [fetch_index_option_chain() lines 470-480](backend/app/engine/option_signal_generator.py#L470)

```python
is_stock = index_name in NIFTY_50_SYMBOLS

if is_stock:
    # Stock symbols: look for tradingsymbols that start with the stock symbol
    options = [
        i for i in instruments 
        if i.get("tradingsymbol", "").startswith(index_name) 
        and i["segment"] == segment
    ]
else:
    # Index symbols: match by name
    options = [i for i in instruments if i["name"] == name and i["segment"] == segment]
```

**Key Difference:**
- **Indices**: Matched by `name` field in instruments
- **Stocks**: Matched by `tradingsymbol` prefix (e.g., "TCS" matches "TCSCE4800CE")

---

## Filtering Stages That Exclude Stocks

### Stage 1: Backend Quality Filtering

**Location:** [select_best_signal()](backend/app/engine/option_signal_generator.py#L916)

Signals must pass:
1. **Error check** - Skip signals with error field
2. **Symbol validation** - Must have non-empty symbol
3. **Entry price validation** - Must be > 0
4. **Quality filter (two-tier)**:
   - Strict: `quality_score >= 85`
   - Fallback: `quality_score >= 75`
5. **Risk:Reward filter (1.3:1 minimum)**

**Why stocks might be excluded:**
- Stock options may have lower quality scores due to different volatility/data availability
- Stock option entry prices might fall outside expected ranges

### Stage 2: Frontend Market Scan Filtering

**Location:** [scanMarketForQualityTrades()](frontend/src/components/AutoTradingDashboard.jsx#L1000)

**Filter 1 - Basic validation:**
```javascript
const scanCandidates = allSignals.filter((signal) => {
  if (!signal || !signal.symbol || !signal.action) return false;
  const entry = Number(signal.entry_price ?? 0);
  const target = Number(signal.target ?? 0);
  const stop = Number(signal.stop_loss ?? 0);
  if (!(entry > 0) || !(target > 0) || !(stop > 0)) return false;
  if (signal.action === 'BUY' && !(target > entry && stop < entry)) return false;
  if (signal.action === 'SELL' && !(target < entry && stop > entry)) return false;
  return true;
});
```

**Filter 2 - Quality, confidence, and RR (Stage 1):**
```javascript
const cleanFiltered = qualityScores
  .filter((s) => {
    const confidence = Number(s.confirmation_score ?? s.confidence ?? 0);
    const rr = Number(s.rr ?? 0);
    return s.quality >= safeMinQuality && confidence >= 65 && rr >= 1.1;
  })
```

**Filter 3 - Adaptive fallback (Stage 2):**
When strict set is empty, falls back to:
```javascript
.filter((s) => {
  const confidence = Number(s.confirmation_score ?? s.confidence ?? 0);
  const rr = Number(s.rr ?? 0);
  return s.quality >= 65 && confidence >= 60 && rr >= 1.0;
})
```

**Filter 4 - Momentum alignment check:**
```javascript
// CRITICAL: Momentum alignment check
const indexMomentum = momentumAnalysis[s.index];
if (indexMomentum && indexMomentum.score < 50) return false;

// For stocks without index-level data, check technical indicators
if (!indexMomentum) {
  const tech = s.technical_indicators || {};
  const rsi = Number(tech.rsi ?? 50);
  const macdCross = String(tech.macd?.crossover || '').toLowerCase();
  const techBullish = (rsi >= 40 && rsi <= 75) && (macdCross === 'bullish' || macdCross === '');
  if (!techBullish) return false;
}
```

**Why stocks are excluded here:**
- Stocks may have lower quality scores
- Stocks may not have index-level momentum data (fallback to technical check)
- Technical indicator requirements may not be met
- Price sanity check: `if (s.entry_price < 15) return false;` (allows stock options)

### Stage 3: Active Scan Stability Filter

**Location:** [scanMarketForQualityTrades() lines 1040-1070](frontend/src/components/AutoTradingDashboard.jsx#L1040)

```javascript
const stage3 = adaptiveSource.filter((signal) => {
  const key = `${getUnderlyingRoot(signal)}:${signal.option_type || ''}:${signal.action || ''}`;
  const meta = nextStability.get(key);
  const confidence = Number(signal.confirmation_score ?? signal.confidence ?? 0);
  return Number(signal.quality || 0) >= 85 || confidence >= 75 || (meta?.seenCount || 0) >= 2;
});
```

**Why stocks are excluded:**
- Must have quality >= 85 OR confidence >= 75 OR been seen twice
- Stock signals appearing for first time with moderate scores are excluded
- Leads to only "stable" signals being shown

---

## Known Issue: Timeout/Cache Problem

**Location:** [memory/repo/market-scan-timeout-cache.md](memories/repo/market-scan-timeout-cache.md)

**Root Cause:**
- Broad `/option-signals/intraday-advanced` scans can timeout when scanning 40+ symbols
- Returns `status=timeout_using_cache` with stale (index-only) cached results
- Frontend correctly skips timeout-cache for broad requests BUT may retry with narrower searches

**Impact on Stocks:**
- A timeout on a stock-inclusive scan falls back to index-only results
- Users see only 4 index signals instead of mixed stock+index signals

**Workaround in Frontend:**

**Location:** [AutoTradingDashboard.jsx lines 843-870](frontend/src/components/AutoTradingDashboard.jsx#L843)

```javascript
const requestsToTry = [
  // Smaller FNO batch first - lower load, better chance to return stocks quickly
  `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=12`,
  // Broad scan (tries to include FNO universe - may timeout on heavy load)
  `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=40`,
  // Nifty-only fallback (indices)
  `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true`,
  // Generic fallback - whatever the API returns
  `${OPTION_SIGNALS_API}?mode=${modeParam}`,
];

// Skip timeout cache for broad scans
if (isTimeoutCache && requestedBroadUniverse) {
  continue; // Don't use timeout cache, try next narrower request
}
```

---

## API Endpoint Differences

### `/option-signals/intraday` (Basic)
**Location:** [option_signals.py](backend/app/routes/option_signals.py)

```python
@router.get("/intraday")
def get_intraday_option_signals():
    return {"signals": generate_signals()}
```

**Behavior:**
- Always uses defaults: `include_nifty50=False, include_fno_universe=False`
- **Returns only 4 index signals** (BANKNIFTY, NIFTY, SENSEX, FINNIFTY)
- NO stock signals

### `/option-signals/intraday-advanced` (Advanced)
**Location:** [option_signals.py](backend/app/routes/option_signals.py#L9)

```python
@router.get("/intraday-advanced")
async def get_intraday_option_signals_advanced(
    mode: str = "balanced",
    symbols: str | None = None,
    include_nifty50: bool = False,
    include_fno_universe: bool = False,
    max_symbols: int = 60,
):
```

**Behavior:**
- Accepts `include_nifty50=true` to include NIFTY 50 stocks
- Accepts `include_fno_universe=true` to include broader F&O universe
- **Can return stock signals if parameters are set**
- Returns cached results on timeout (may be index-only)

---

## Quality Scoring Breakdown

### Signal Quality Calculation

**Location:** [_validate_signal_quality()](backend/app/engine/option_signal_generator.py#L113)

Quality score comprises multiple factors:

**1. Technical Indicators (if enabled):**
- RSI factor (0-20 points)
  - 30-70 range: 20 points (healthy)
  - <30 (oversold): 15 points
  - >70 (overbought): 0 points
- MACD factor (0-20 points)
  - Bullish crossover: 20 points
  - Positive histogram: 10 points
- Bollinger Bands factor (0-20 points)
  - <0.3 (lower band): 20 points
  - 0.4-0.6 (mid-range): 10 points
- Technical recommendation (0-20 points)
  - STRONG BUY/BUY: 20 points
  - HOLD: 10 points

**2. Basic Factors (always evaluated):**
- Volume Analysis (0-10 points)
  - >1.5x average: 10 points
  - >1.2x average: 5 points
- Candle Close Position (0-10 points)
  - >70% of range (near high): 10 points
  - >50% (above mid): 5 points
- Trend Context (0-10 points)
  - >1% move: 10 points
  - >0.5% move: 5 points

**Minimum Passing Thresholds:**
- Strict: `quality_score >= 85` (for best signal selection)
- Fallback: `quality_score >= 75` (if no 85+ available)
- Frontend display: `quality >= safeMinQuality` (user-configurable, default 75-85)

**Why stocks score lower:**
- Stock technical indicators may be noisier
- Stock volume metrics may be different from index metrics
- Stock options have different average premium levels
- Limited historical data for some stocks

---

## Key Configuration Parameters

### Backend (`generate_signals()`)
| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| `include_nifty50` | `False` | True/False | **Controls if NIFTY 50 stocks included** |
| `include_fno_universe` | `False` | True/False | **Controls if F&O universe (beyond NIFTY 50) included** |
| `max_symbols` | 120 | 1-300 | Caps total symbols scanned |
| `symbols` | None | Custom list | Override default symbol universe |

### Frontend (`scanMarketForQualityTrades()`)
| Parameter | Default | Impact |
|-----------|---------|--------|
| `minQuality` | 75-85 | Minimum quality % to display signals |
| `scannerMinQuality` | User setting | Frontend display threshold |

---

## Signal Type Classification

### How System Determines "Stock" vs "Index"

**Backend (Lines 470-475):**
```python
is_stock = index_name in NIFTY_50_SYMBOLS
```

**Frontend (Lines 592-604):**
```javascript
const getSignalGroup = (signal) => {
  // Check new signal_type field from backend (preferred)
  if (signal?.signal_type) {
    return signal.signal_type === 'stock' ? 'stocks' : 'indices';
  }
  // Fallback to name-based heuristics if signal_type not present
  const indexName = String(signal?.index || '').toUpperCase();
  if (INDEX_SYMBOLS.has(indexName)) return 'indices';
  const symbol = String(signal?.symbol || '').toUpperCase();
  for (const idx of INDEX_SYMBOLS) {
    if (symbol.includes(idx)) return 'indices';
  }
  return 'stocks';
};
```

### Signal Type Field

**Backend sets `signal_type` field:**
- `"index"` for BANKNIFTY, NIFTY, SENSEX, FINNIFTY
- `"stock"` for NIFTY 50 symbols (TCS, INFY, RELIANCE, etc.)

This field is returned in every signal for proper classification.

---

## NIFTY 50 Symbols Supported (Lines 26-43)

```
ADANIENT, ADANIPORTS, APOLLOHOSP, ASIANPAINT, AXISBANK,
BAJAJ-AUTO, BAJFINANCE, BAJAJFINSV, BEL, BPCL,
BHARTIARTL, BRITANNIA, CIPLA, COALINDIA, DRREDDY,
EICHERMOT, GRASIM, HCLTECH, HDFCBANK, HDFCLIFE,
HEROMOTOCO, HINDALCO, HINDUNILVR, ICICIBANK, INDUSINDBK,
INFY, ITC, JSWSTEEL, KOTAKBANK, LT,
M&M, MARUTI, NESTLEIND, NTPC, ONGC,
POWERGRID, RELIANCE, SBIN, SBILIFE, SHRIRAMFIN,
SUNPHARMA, TATAMOTORS, TATASTEEL, TCS, TECHM,
TITAN, ULTRACEMCO, WIPRO
```

---

## Why Stocks Might Not Be Getting Signals

### ✗ Reason 1: Default Configuration
- `/option-signals/intraday` endpoint uses defaults
- Defaults: `include_nifty50=False` (no stocks!)
- **Solution**: Use `/option-signals/intraday-advanced?include_nifty50=true`

### ✗ Reason 2: Timeout on Broad Scans
- Scanning 40+ symbols takes time
- API times out after 40 seconds
- Returns `status=timeout_using_cache` with old index-only results
- **Solution**: Backend should cap per-symbol work; Frontend already retries smaller batches

### ✗ Reason 3: Lower Quality Scores
- Stock options might score 70-80 (below 85+ for best selection)
- Gets selected in fallback round but might not display
- **Solution**: Stocks included, but may appear lower in rankings

### ✗ Reason 4: No Momentum Data
- Stock signals don't have index-level momentum
- Falls back to technical indicator check
- May filter out if RSI or MACD not in range
- **Solution**: Technical indicator fallback already in place (lines 950-970)

### ✗ Reason 5: Stability Filter
- Stock signals need to be seen 2+ times to stick
- First appearance with moderate quality is excluded
- **Solution**: Signals accumulate in cache, show on second scan

### ✗ Reason 6: User Settings
- `include_fno_universe=false` by default
- Only basic NIFTY 50 stocks included if `include_nifty50=true`
- **Solution**: Check API parameter values in requests

---

## Files Summary

| File | Purpose | Key Lines |
|------|---------|-----------|
| [backend/app/engine/option_signal_generator.py](backend/app/engine/option_signal_generator.py) | Core signal generation | 26-43 (stocks), 748-775 (universe), 778-900 (generate), 470-480 (stock detection) |
| [backend/app/routes/option_signals.py](backend/app/routes/option_signals.py) | API endpoints | Default params disable stocks |
| [frontend/.../AutoTradingDashboard.jsx](frontend/src/components/AutoTradingDashboard.jsx) | Dashboard & filtering | 592-604 (classification), 807-1100 (scanning), 1584-1700 (filtering) |
| [backend/tests/test_stock_option_signals.py](backend/tests/test_stock_option_signals.py) | Test suite | Documents expected behavior |

---

## Recommendations

### To Debug Why Stocks Aren't Showing

1. **Check API endpoint:**
   - Is `/option-signals/intraday` or `/option-signals/intraday-advanced` being called?
   - Is `include_nifty50=true` being passed?

2. **Check request parameters:**
   ```
   ✓ /option-signals/intraday-advanced?include_nifty50=true&include_fno_universe=true&max_symbols=40
   ✗ /option-signals/intraday (uses defaults, no stocks)
   ```

3. **Check signal response:**
   - Are signals coming back with `signal_type: "stock"`?
   - Are they being filtered by quality/confidence thresholds?
   - Check browser console for filtering logs

4. **Check quality scores:**
   - Stock signals should have `quality_score` field
   - If < 75, they'll be filtered out in strict mode
   - Check `quality_factors` field for why score is low

5. **Check timeout behavior:**
   - Is `/intraday-advanced?max_symbols=40` timing out?
   - Frontend logs should show "timeout_using_cache"
   - Should retry with smaller batches automatically

### To Enable Stock Signals

**Backend:**
- Ensure `/option-signals/intraday-advanced` endpoint is being called
- Pass `include_nifty50=true` parameter
- Optionally pass `include_fno_universe=true` for more stocks

**Frontend:**
- Dashboard should auto-request with stock parameters
- Check `scanMarketForQualityTrades()` request URLs
- Verify `INDEX_SYMBOLS` set matches backend (lines 602-606)

### To Improve Stock Signal Quality

1. **Reduce quality threshold for stocks:**
   - Current: 75-85 points
   - Consider: 70-80 for stocks (more volatile, noisier data)

2. **Adjust technical indicator thresholds:**
   - Stock options react faster than index options
   - May need RSI range adjustment (e.g., 35-75 instead of 30-70)

3. **Account for stock-specific factors:**
   - Different lot sizes (typically 1 vs 50 for NIFTY)
   - Different IV levels
   - Different liquidity patterns

---

## Test Coverage

**File:** [backend/tests/test_stock_option_signals.py](backend/tests/test_stock_option_signals.py)

**Key tests:**
- `TestStockSymbolDetection`: Verify stocks are identified correctly
- `TestStockOptionSignalStructure`: Verify signal structure
- `TestStockSignalFiltering`: Verify signals pass quality filters
- `TestFetchStockOptionChain`: Verify option chain fetching for stocks
- `TestSignalGenerationWithStocks`: Verify backend generates stock signals
- `TestStockSignalIntegration`: Integration tests for mixed stock+index signals
- `TestSignalQualityValidation`: Quality threshold validation

**Run tests:**
```bash
cd backend
pytest tests/test_stock_option_signals.py -v
```

---

## Conclusion

**Stock signals ARE being generated**, but may not appear due to:
1. Default configuration (API endpoint not requesting stocks)
2. Timeout issues on broad scans returning cached index-only results
3. Filtering stages removing signals with lower quality scores
4. Multiple filtering layers that prefer signals with highest stability/confidence

The infrastructure is in place and working correctly. The issue is typically one of:
- **Configuration**: Not requesting stocks via API parameters
- **Timeout**: Broad scans timing out and falling back to cached results
- **Visibility**: Stocks scoring lower and appearing lower in rankings or being filtered out
