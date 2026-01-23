import sqlite3

conn = sqlite3.connect('F:/ALGO/algotrade.db')
cursor = conn.cursor()
cursor.execute('SELECT id, user_id, broker_name, access_token, created_at FROM broker_credentials ORDER BY id')
rows = cursor.fetchall()
print('\n' + '='*60)
print('ALL BROKER CREDENTIALS')
print('='*60)
for r in rows:
    print(f'ID={r[0]}, User={r[1]}, Broker={r[2]}, Created={r[4]}')
    print(f'  Has Token: {bool(r[3])}')
    if r[3]:
        print(f'  Token: {r[3][:30]}...')
    print()
print('='*60)
conn.close()
