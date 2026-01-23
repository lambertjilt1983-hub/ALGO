import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

c.execute('SELECT id, user_id, broker_name, access_token FROM broker_credentials WHERE id = 4')
broker = c.fetchone()

print('Broker ID 4 Details:')
print(f'ID: {broker[0]}')
print(f'User: {broker[1]}')
print(f'Name: {broker[2]}')

if broker[3]:
    print(f'Token: {broker[3][:50]}...')
    print(f'Token Length: {len(broker[3])} chars')
    print('Status: HAS ACCESS TOKEN')
else:
    print('Token: NULL')
    print('Status: NO ACCESS TOKEN')

conn.close()
