import sqlite3

# Path to your SQLite database
DB_PATH = 'F:/ALGO/algotrade.db'

# SQL to create the broker_credentials table
CREATE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS broker_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    broker_name TEXT,
    api_key TEXT,
    api_secret TEXT,
    access_token TEXT,
    refresh_token TEXT,
    token_expiry DATETIME,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
'''

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("[SUCCESS] broker_credentials table created (if not already present).")
    conn.close()
