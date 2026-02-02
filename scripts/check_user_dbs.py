import sqlite3
from pathlib import Path

paths = [Path('f:/ALGO/backend/local.db'), Path('f:/ALGO/local.db')]
for p in paths:
    print(f"\nDB: {p}")
    if not p.exists():
        print('  not found')
        continue
    conn = sqlite3.connect(p)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cur.fetchone():
            print('  users table not found')
            continue
        cur.execute("SELECT username, is_email_verified, is_mobile_verified FROM users WHERE username='lambert'")
        row = cur.fetchone()
        print('  user:', row)
    finally:
        conn.close()
