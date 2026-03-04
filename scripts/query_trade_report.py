import sqlite3
import json
import sys
import os

# add backend path so we can import configuration
sys.path.append("backend")
from app.core.config import get_settings
from app.core import database

settings = get_settings()
# derive DB file from engine url if using sqlite
engine_url = str(database.engine.url)
if engine_url.startswith("sqlite:///"):
    DB = engine_url.replace("sqlite://", "")
else:
    # fallback to a known file
    DB = os.path.join(os.getcwd(), "algotrade.db")

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else 'BANKNIFTY26MAR58900PE'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
# Inspect tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
result = {'tables': tables, 'matches': []}

for table in tables:
    try:
        q = f"SELECT * FROM {table} WHERE symbol=? ORDER BY exit_time DESC LIMIT 5"
        cur.execute(q, (SYMBOL,))
        rows = cur.fetchall()
        if rows:
            out = []
            for r in rows:
                out.append(dict(r))
            result['matches'].append({'table': table, 'rows': out})
    except Exception:
        # skip tables without symbol/exit_time columns
        continue

print(json.dumps(result, default=str, indent=2))

conn.close()
