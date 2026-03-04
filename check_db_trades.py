import sqlite3, json
con = sqlite3.connect('backend/algotrade.db')
cur = con.cursor()
cur.execute("SELECT id, symbol, status, entry_time, entry_price FROM trade_reports ORDER BY id DESC LIMIT 10")
rows = cur.fetchall()
print("Recent TradeReports:")
print(rows)
con.close()
