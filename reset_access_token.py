import sys
sys.path.insert(0, 'f:/ALGO/backend')
import sqlite3

# Reset access token for broker 4
conn = sqlite3.connect('F:/ALGO/algotrade.db')
cursor = conn.cursor()

print("Before:")
cursor.execute('SELECT id, access_token FROM broker_credentials WHERE id = 4')
print(cursor.fetchone())

cursor.execute('UPDATE broker_credentials SET access_token = NULL WHERE id = 4')
conn.commit()

print("\nAfter:")
cursor.execute('SELECT id, access_token FROM broker_credentials WHERE id = 4')
print(cursor.fetchone())

conn.close()
print("\n✓ Access token cleared! You can now re-authenticate with Zerodha.")
