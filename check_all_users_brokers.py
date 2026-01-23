import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

# Check all users
c.execute('SELECT id, username, email FROM users')
users = c.fetchall()

print("All Users:")
print("=" * 60)
for user in users:
    print(f"ID: {user[0]}, Username: {user[1]}, Email: {user[2]}")
    
    # Check brokers for this user
    c.execute('SELECT id, broker_name, access_token FROM broker_credentials WHERE user_id = ?', (user[0],))
    brokers = c.fetchall()
    
    if brokers:
        for broker in brokers:
            token_status = "HAS TOKEN" if broker[2] else "NO TOKEN"
            print(f"  -> Broker ID: {broker[0]}, Name: {broker[1]}, Status: {token_status}")
    else:
        print(f"  -> No brokers")
    print()

conn.close()
