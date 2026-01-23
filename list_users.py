import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

c.execute('SELECT id, username, email FROM users')
users = c.fetchall()

print("All users in database:")
print("-" * 50)
if users:
    for user in users:
        print(f"ID: {user[0]}, Username: {user[1]}, Email: {user[2]}")
else:
    print("No users found!")

conn.close()
