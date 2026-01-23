import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
cursor = conn.cursor()

# Check if broker 5 exists
cursor.execute('SELECT id FROM broker_credentials WHERE id = 5')
if cursor.fetchone():
    cursor.execute('DELETE FROM broker_credentials WHERE id = 5')
    conn.commit()
    print('✓ Deleted broker 5')
else:
    print('✓ Broker 5 does not exist')

# Show current brokers
cursor.execute('SELECT id, broker_name, user_id FROM broker_credentials')
rows = cursor.fetchall()
print('\nCurrent brokers:')
for r in rows:
    print(f'  ID={r[0]}, Broker={r[1]}, User={r[2]}')

conn.close()
