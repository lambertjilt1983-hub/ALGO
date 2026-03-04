import sys
sys.path.insert(0, 'backend')
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models.trading import TradeReport

settings = get_settings()
print(f"DATABASE_URL config: {settings.DATABASE_URL}")
print(f"Engine URL: {engine.url}")

db = SessionLocal()
try:
    # Query OPEN reports like the endpoint code does
    reports = db.query(TradeReport).filter(TradeReport.status == "OPEN").all()
    print(f"OPEN reports in DB: {len(reports)}")
    for r in reports:
        print(f"  {r.id}: {r.symbol} {r.quantity}x{r.entry_price} (status={r.status} entry_time={r.entry_time})")
        resp = {
            "symbol": r.symbol,
            "quantity": r.quantity,
            "entry_price": r.entry_price,
            "current_price": None,
            "side": r.side,
            "status": "OPEN",
            "entry_time": r.entry_time.isoformat() if r.entry_time else None,
            "meta": r.meta,
        }
        print(f"  Response obj: {resp}")
finally:
    db.close()
