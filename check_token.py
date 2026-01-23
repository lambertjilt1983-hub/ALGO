import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

c.execute('SELECT id, broker_name, access_token FROM broker_credentials WHERE id = 4')
broker = c.fetchone()

if broker:
    print(f'Broker ID: {broker[0]}')
    print(f'Broker Name: {broker[1]}')
    if broker[2]:
        print(f'Access Token: {broker[2][:50]}...')
        print('Status: Token EXISTS - Should show real data')
    else:
        print('Access Token: None')
        print('Status: No token - Will show demo data')
else:
    print('Broker 4 not found!')

conn.close()
