import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from app.core.database import SessionLocal
from app.models.trading import TradeReport
from datetime import datetime
import urllib.request, json

db=SessionLocal()
report=TradeReport(symbol='TESTOPEN', side='BUY', quantity=1, entry_price=100, status='OPEN', entry_time=datetime.utcnow(), trading_date=datetime.utcnow().date())
db.add(report); db.commit()
print('inserted open report id', report.id)
try:
    resp = urllib.request.urlopen('http://localhost:8002/autotrade/trades/active')
    print(resp.read().decode())
except Exception as e:
    print('fetch error', e)
db.close()
