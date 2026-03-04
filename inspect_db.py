import sqlite3, json
from datetime import datetime
paths = [r"backend\\algotrade.db", r"algotrade.db", r"algotrade_qa.db", r"local.db", r"backend\\local.db"]
for path in paths:
    print('--- DB:', path)
    con = sqlite3.connect(path)
    cur = con.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        print('TABLES:', tables)
        if 'trade_reports' in tables:
            cur.execute("PRAGMA table_info('trade_reports');")
            cols = cur.fetchall()
            print('SCHEMA:', cols)

            cur.execute('SELECT id, symbol, status, entry_time, quantity, entry_price, meta FROM trade_reports ORDER BY id;')
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    'id': r[0], 'symbol': r[1], 'status': r[2], 'entry_time': r[3], 'quantity': r[4], 'entry_price': r[5], 'meta': r[6]
                })
            print(json.dumps(out, default=str, indent=2))
        else:
            print('No trade_reports table')
    except Exception as e:
        print('ERR', e)
    finally:
        con.close()
    

con = sqlite3.connect(path)
cur = con.cursor()
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    print('TABLES:', tables)
    if 'trade_reports' in tables:
        cur.execute('SELECT id, symbol, status, entry_time, quantity, entry_price, meta FROM trade_reports ORDER BY id;')
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                'id': r[0], 'symbol': r[1], 'status': r[2], 'entry_time': r[3], 'quantity': r[4], 'entry_price': r[5], 'meta': r[6]
            })
        print(json.dumps(out, default=str, indent=2))
    else:
        print('No trade_reports table')
except Exception as e:
    print('ERR', e)
finally:
    con.close()
