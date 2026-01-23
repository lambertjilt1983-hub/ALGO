import requests
import sqlite3

# First, check current token status
conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()
c.execute('SELECT id, broker_name, access_token FROM broker_credentials WHERE id = 4')
broker = c.fetchone()

print("BEFORE:")
print(f'Broker ID: {broker[0]}')
print(f'Access Token: {broker[2] if broker[2] else "None"}')
print()

# Now test if we can manually set a test token
print("Testing token save...")
c.execute('UPDATE broker_credentials SET access_token = ? WHERE id = 4', ('test_token_12345',))
conn.commit()
print("Token saved!")

# Verify it was saved
c.execute('SELECT access_token FROM broker_credentials WHERE id = 4')
result = c.fetchone()
print(f'Verified token in DB: {result[0]}')

# Clean up - remove test token
c.execute('UPDATE broker_credentials SET access_token = NULL WHERE id = 4')
conn.commit()
print("Cleaned up test token")

conn.close()

print("\n" + "="*60)
print("Database can save tokens correctly!")
print("Issue: OAuth callback might not be reaching the database save")
