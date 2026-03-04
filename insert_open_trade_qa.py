import sqlite3, json
from datetime import datetime
path = r"algotrade_qa.db"
con = sqlite3.connect(path)
cur = con.cursor()
now = datetime.utcnow().isoformat(sep=' ')
try:
    cur.execute("INSERT INTO trade_reports (symbol, side, quantity, entry_price, status, entry_time, meta) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ('TESTSYM', 'BUY', 1.0, 100.0, 'OPEN', now, json.dumps({'test': True})))
    con.commit()
    print('Inserted id', cur.lastrowid)
    cur.execute('SELECT id, symbol, status FROM trade_reports ORDER BY id DESC LIMIT 5')
    rows = cur.fetchall()
    print('Recent rows:', rows)
except Exception as e:
    print('ERR', e)
finally:
    con.close()
