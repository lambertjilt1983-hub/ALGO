import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')

print("USERS:")
for row in conn.execute('SELECT id, username FROM users'):
    print(f"  ID {row[0]}: {row[1]}")

print("\nBROKERS WITH CREDENTIALS:")
for row in conn.execute('SELECT id, broker_name, user_id, access_token, api_key FROM broker_credentials'):
    broker_id, broker_name, user_id, access_token, api_key = row
    print(f"  Broker {broker_id} ({broker_name}) - User: {user_id}")
    print(f"    API Key (first 40 chars): {api_key[:40] if api_key else 'None'}")
    print(f"    Access Token (first 40 chars): {access_token[:40] if access_token else 'None'}")
    print(f"    Access Token Length: {len(access_token) if access_token else 0}")

conn.close()
