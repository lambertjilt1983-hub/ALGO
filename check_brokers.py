import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

c.execute('SELECT id, user_id, broker_name, api_key FROM broker_credentials')
brokers = c.fetchall()

print("All brokers in database:")
print("-" * 60)
if brokers:
    for broker in brokers:
        print(f"ID: {broker[0]}, User: {broker[1]}, Broker: {broker[2]}, API Key: {broker[3][:20]}...")
else:
    print("No brokers found!")

print("\nAll users:")
print("-" * 60)
c.execute('SELECT id, username FROM users')
users = c.fetchall()
for user in users:
    print(f"ID: {user[0]}, Username: {user[1]}")

conn.close()
