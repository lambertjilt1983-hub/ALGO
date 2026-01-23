import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
cursor = conn.cursor()
cursor.execute('SELECT id, user_id, broker_name, access_token FROM broker_credentials')
rows = cursor.fetchall()
print('\n' + '='*60)
print('BROKER CREDENTIALS IN DATABASE')
print('='*60)
for r in rows:
    print(f'  ID={r[0]}, User={r[1]}, Broker={r[2]}')
    print(f'    Has Token: {bool(r[3])}')
    if r[3]:
        print(f'    Token: {r[3][:50]}...')
    else:
        print(f'    Token: NONE')
    print()
print('='*60)
conn.close()
