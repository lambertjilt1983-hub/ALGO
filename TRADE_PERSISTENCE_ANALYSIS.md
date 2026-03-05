# Trade Persistence & Active Trade Management Analysis

## 1. THE THREE ENDPOINTS

### Endpoint 1: POST `/autotrade/execute`
**File:** [backend/app/routes/auto_trading_simple.py](backend/app/routes/auto_trading_simple.py#L1550-L1810)

**What it does:**
1. Validates trade request (stop loss, target, quantity, margin)
2. **Creates a TradeReport record in database with status="OPEN"** (line 1714-1722)
3. Places order to Zerodha broker
4. **Appends trade to in-memory `active_trades` list if order succeeds** (line 1766)

**Key code for persistence:**
```python
# Lines 1708-1722: Create initial database record
report = TradeReport(
    symbol=trade_obj.get("symbol"),
    side=trade_obj.get("side"),
    quantity=trade_obj.get("quantity"),
    entry_price=trade_obj.get("price"),
    status="OPEN",                    # ← Initially OPEN
    entry_time=entry_dt,
    trading_date=entry_dt.date(),
    meta={"support": trade_obj.get("support"), "resistance": trade_obj.get("resistance")},
)
db.add(report)
db.commit()
trade_obj["report_id"] = report.id   # Store DB ID for later updates

# Lines 1753-1766: Append to in-memory list after Zerodha success
if real_order["success"]:
    active_trades.append(trade_obj)   # ← Trade added to memory
```

**Status flow for execute:**
- `OPEN` → (when closed) → `CLOSED`
- `OPEN` → (if rejected) → `REJECTED`

---

### Endpoint 2: GET `/paper-trades/active`
**File:** [backend/app/routes/paper_trading.py](backend/app/routes/paper_trading.py#L94-L118)

**What it does:**
- Queries **PaperTrade model** (NOT TradeReport)
- Filters for `status == "OPEN"`
- Returns demo/signal tracking trades

**Key code:**
```python
@router.get("/paper-trades/active")
def get_active_paper_trades(db: Session = Depends(get_db)):
    """Get all open paper trades"""
    trades = db.query(PaperTrade).filter(
        PaperTrade.status == "OPEN"   # ← Filter for OPEN status
    ).order_by(PaperTrade.entry_time.desc()).all()
    
    return {
        "success": True,
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "current_price": t.current_price,
                "pnl": t.pnl,
                "pnl_percentage": t.pnl_percentage,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            }
            for t in trades
        ]
    }
```

**Status values in PaperTrade:**
- `OPEN` - Active trade
- `TARGET_HIT` - Target reached
- `SL_HIT` - Stop loss hit
- `EXPIRED` - End of day close

---

### Endpoint 3: GET `/autotrade/trades/active` (LIVE TRADES)
**File:** [backend/app/routes/auto_trading_simple.py](backend/app/routes/auto_trading_simple.py#L1819-L1900)

**What it does (Three-tier fallback strategy):**

1. **Tier 1: Live broker positions** - Fetches from Zerodha API
2. **Tier 2: In-memory active_trades list** - If no broker data
3. **Tier 3: Database TradeReport with status=OPEN** - Fallback persistence

**Key code:**
```python
@router.get("/trades/active")
async def get_active_trades(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    token: str = Depends(AuthService.verify_bearer_token),
):
    """Return list of currently open trades"""
    
    logging.info(f"[API /trades/active] [START] Memory active_trades count: {len(active_trades)}")
    trades = list(active_trades)  # copy
    
    # TIER 1: Try to get LIVE broker positions
    try:
        cred = BrokerAuthService.get_credentials(user_id=user_id, broker_name="zerodha", db=db)
        executor = OrderExecutor("zerodha", {...credentials...})
        positions = await executor.get_positions()
        
        if positions:
            broker_trades = []
            for pos in positions:
                broker_trades.append({
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "entry_price": getattr(pos, "average_price", None) or getattr(pos, "entry_price", None),
                    "current_price": getattr(pos, "last_price", None),
                    "side": pos.side,
                    "status": "OPEN",
                })
            trades = broker_trades  # ← OVERRIDE with broker data
            logging.info(f"[API /trades/active] [BROKER] Overriding with {len(trades)} broker positions")
    except Exception as e:
        logging.warning(f"[API /trades/active] failed to fetch broker positions: {e}")
    
    # TIER 3: Fallback to database OPEN records if no broker data
    if not trades:
        try:
            reports = db.query(TradeReport).filter(TradeReport.status == "OPEN").all()
            logging.info(f"[API /trades/active] [DB] Open TradeReport count: {len(reports)}")
            if reports:
                trades = []
                for r in reports:
                    trades.append({
                        "symbol": r.symbol,
                        "quantity": r.quantity,
                        "entry_price": r.entry_price,
                        "current_price": None,
                        "side": r.side,
                        "status": "OPEN",
                        "entry_time": r.entry_time.isoformat() if r.entry_time else None,
                        "meta": r.meta,
                    })
        except Exception as e:
            logging.warning(f"[API /trades/active] failed to query database: {e}")
    
    return {"trades": trades}
```

---

## 2. DATABASE MODELS & TABLES

### Model 1: TradeReport (LIVE/EXECUTED TRADES)
**File:** [backend/app/models/trading.py](backend/app/models/trading.py#L80-L99)
**Table:** `trade_reports`

**Purpose:** Persistent log of live trades (executed via Zerodha)

**Key Fields:**
```python
class TradeReport(Base):
    __tablename__ = "trade_reports"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)           # NIFTY23JUN20750CE
    side = Column(String, index=True)              # BUY, SELL
    quantity = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float)                     # NULL while OPEN
    pnl = Column(Float)                            # NULL while OPEN
    pnl_percentage = Column(Float)
    strategy = Column(String, nullable=True)
    status = Column(String, default="CLOSED")      # ← KEY: OPEN, CLOSED, REJECTED
    entry_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, default=datetime.utcnow, index=True)
    trading_date = Column(Date, default=func.current_date(), index=True)
    meta = Column(JSON, nullable=True)             # Stores support, resistance, broker error
```

**Status values for TradeReport:**
- `OPEN` - Trade is active (newly created)
- `CLOSED` - Trade has exited (SL hit, target hit, or closed)
- `REJECTED` - Zerodha rejected the order

---

### Model 2: PaperTrade (DEMO/SIGNAL TRACKING)
**File:** [backend/app/models/trading.py](backend/app/models/trading.py#L102-L124)
**Table:** `paper_trades`

**Purpose:** Track signal performance in paper trading mode (no real execution)

**Key Fields:**
```python
class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, default=1)
    symbol = Column(String, index=True)
    index_name = Column(String, nullable=True)    # NIFTY, BANKNIFTY
    side = Column(String)                          # BUY, SELL
    signal_type = Column(String)                   # CE, PE, or equity
    quantity = Column(Float)
    entry_price = Column(Float)
    current_price = Column(Float, nullable=True)   # Updated in real-time
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    status = Column(String, default="OPEN", index=True)  # ← KEY
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)             # Calculated from current_price
    pnl_percentage = Column(Float, nullable=True)
    strategy = Column(String, default="professional")
    signal_data = Column(JSON, nullable=True)
    entry_time = Column(DateTime, default=datetime.utcnow, index=True)
    exit_time = Column(DateTime, nullable=True)
    trading_date = Column(Date, default=func.current_date(), index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Status values for PaperTrade:**
- `OPEN` - Trade is active
- `TARGET_HIT` - Target price reached
- `SL_HIT` - Stop loss hit
- `EXPIRED` - Closed at end of day (via `/paper-trades/close-all`)

---

## 3. HOW TRADES ARE MARKED AS "ACTIVE"

### What makes a trade "active"?

| Source | Active Condition | Status Value |
|--------|------------------|--------------|
| **Live Broker** | Currently open position in Zerodha | `"OPEN"` (inferred) |
| **Database TradeReport** | `status == "OPEN"` | `"OPEN"` |
| **Database PaperTrade** | `status == "OPEN"` | `"OPEN"` |
| **In-memory active_trades** | `"status": "OPEN"` in dict | `"OPEN"` |

### Trade Closure (No longer "active"):

**TradeReport:**
```python
# Line 715-750: When trade is closed
report.status = trade.get("status") or "CLOSED"  # Changed from OPEN → CLOSED
report.exit_price = exit_price
report.exit_time = exit_dt
report.pnl = round(pnl, 2)
report.pnl_percentage = round(pnl_percentage, 2)
db.commit()
```

**PaperTrade:**
```python
# Line 333: Close all at end of day
open_trades = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
for trade in open_trades:
    trade.status = "EXPIRED"  # Changed from OPEN → EXPIRED
    trade.exit_time = datetime.utcnow()
db.commit()
```

---

## 4. DIFFERENCE: DEMO vs LIVE MODE STORAGE

### DEMO MODE (`PaperTrade` table)
- **Endpoint:** POST `/paper-trades` 
- **Database Table:** `paper_trades`
- **Execution:** NO real order to broker, only signal tracked
- **Active Query:** `PaperTrade.status == "OPEN"`
- **Retrieval:** GET `/paper-trades/active`
- **Status Values:** OPEN, TARGET_HIT, SL_HIT, EXPIRED
- **Use Case:** Paper trading, backtesting, signal validation

### LIVE MODE (`TradeReport` table)
- **Endpoint:** POST `/autotrade/execute`
- **Database Table:** `trade_reports`
- **Execution:** Real order placed to Zerodha (NFO exchange)
- **Active Query:** `TradeReport.status == "OPEN"`
- **Retrieval:** GET `/autotrade/trades/active` (with 3-tier fallback)
- **Status Values:** OPEN, CLOSED, REJECTED
- **Persistence Layers:**
  1. Live Zerodha broker API
  2. In-memory `active_trades` list
  3. Database `trade_reports` table
- **Use Case:** Live trading with real capital

---

## 5. TRADE PERSISTENCE FLOW DIAGRAM

### Live Trade (TradeReport):
```
POST /autotrade/execute
    ↓
Create TradeReport(status="OPEN") in DB
    ↓
Place order to Zerodha
    ↓
If successful: append to in-memory active_trades[]
    ↓
During trade: 
  - Monitor via /autotrade/trades/active
  - Fallback hierarchy: Broker API → memory → DB
    ↓
Trade closure:
  - Update TradeReport(status="CLOSED")
  - Remove from active_trades[]
  - Calculate final PNL
```

### Paper Trade (PaperTrade):
```
POST /paper-trades
    ↓
Create PaperTrade(status="OPEN") in DB
    ↓
NO broker order
    ↓
Monitor via GET /paper-trades/active
  - Query: PaperTrade.status == "OPEN"
    ↓
Trade closure (manual or end-of-day):
  - Update PaperTrade(status="EXPIRED/SL_HIT/TARGET_HIT")
```

---

## 6. POTENTIAL ISSUES & OBSERVATIONS

### Issue 1: Trade Persistence Mismatch
- **Problem:** Live trades have 3 storage layers (broker, memory, DB) which can desynchronize
- **Example:** If Zerodha shows 5 positions but `active_trades[]` has 3, endpoint returns broker data
- **Risk:** If broker API fails, falls back to stale DB records

### Issue 2: Memory Loss on Restart
- **Problem:** In-memory `active_trades[]` list is cleared on app restart
- **Recovery:** Uses database `TradeReport` records with `status="OPEN"` as fallback
- **Risk:** Trades closed outside the app (e.g., via Zerodha website) may show as still OPEN in DB

### Issue 3: Paper Trade Storage Separate
- **Problem:** Demo trades (`PaperTrade`) and live trades (`TradeReport`) are in different tables
- **Implication:** Cannot easily compare demo vs live strategy performance
- **Workaround:** Both have identical schema structure for easy migration

### Issue 4: Status Field Inconsistency
- **TradeReport:** Uses `status` with default `"CLOSED"` (confusing - new trades created as `"OPEN"`)
- **PaperTrade:** Uses `status` with default `"OPEN"` (clearer)
- **Risk:** Mixing up defaults when queries don't specify status explicitly

---

## 7. KEY TABLES FOR ANALYSIS

### Query Active Live Trades:
```sql
-- From database
SELECT * FROM trade_reports WHERE status = 'OPEN';

-- From Python
trades = db.query(TradeReport).filter(TradeReport.status == "OPEN").all()
```

### Query Active Demo Trades:
```sql
-- From database
SELECT * FROM paper_trades WHERE status = 'OPEN';

-- From Python
trades = db.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()
```

### All Closed Trades (for reporting):
```sql
SELECT * FROM trade_reports WHERE status = 'CLOSED' ORDER BY exit_time DESC;
SELECT * FROM paper_trades WHERE status IN ('EXPIRED', 'SL_HIT', 'TARGET_HIT');
```

---

## 8. FILE REFERENCES SUMMARY

| File | Purpose | Key Lines |
|------|---------|-----------|
| [auto_trading_simple.py](backend/app/routes/auto_trading_simple.py) | Live trading endpoints | 1550-1810 (execute), 1819-1900 (/trades/active), 680-750 (trade closure) |
| [paper_trading.py](backend/app/routes/paper_trading.py) | Demo trading endpoints | 54-120 (create/active) |
| [trading.py](backend/app/models/trading.py) | Database models | 80-99 (TradeReport), 102-124 (PaperTrade) |
| [database.py](backend/app/core/database.py) | Database connection | Session/DB setup |

---

## Conclusion

**How trades are marked as active:**
- Database: `status == "OPEN"` column
- In-memory: `"status": "OPEN"` dict field
- Broker: Positions returned from live API

**Are trades being saved properly?**
- ✅ YES for live trades: Created in DB before broker order, updated on closure
- ✅ YES for demo trades: Created and updated in PaperTrade table
- ⚠️ RISK: In-memory list lost on restart (but DB recovers it)

**Demo vs Live difference:**
- Demo uses `PaperTrade` table, no broker execution
- Live uses `TradeReport` table, places real orders to Zerodha
- Both track status field but with different possible values
