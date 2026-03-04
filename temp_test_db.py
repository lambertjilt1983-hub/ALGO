from app.core.database import SessionLocal
from app.models.trading import TradeReport
from datetime import datetime

if __name__ == '__main__':
    db = SessionLocal()
    report = TradeReport(symbol='UNITTEST', side='BUY', quantity=2, entry_price=123.45, status='OPEN', entry_time=datetime.utcnow(), trading_date=datetime.utcnow().date())
    db.add(report)
    db.commit()
    print('inserted', report.id)
    print('open', [(r.id, r.symbol, r.status) for r in db.query(TradeReport).filter(TradeReport.status=='OPEN').all()])
    db.close()
