import sqlite3
import sys
sys.path.insert(0, 'F:/ALGO/backend')

from app.core.security import encryption_manager

conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

# Delete existing brokers
c.execute('DELETE FROM broker_credentials')
print('Deleted all existing brokers')

# Get test user
c.execute('SELECT id FROM users WHERE username = ?', ('test',))
user = c.fetchone()

if not user:
    print('Error: Test user not found!')
    conn.close()
    exit(1)

user_id = user[0]
print(f'Found user: test (ID: {user_id})')

# Create broker with ID 4
encrypted_key = encryption_manager.encrypt_credentials('[REMOVED_ZERODHA_API_KEY]')
encrypted_secret = encryption_manager.encrypt_credentials('[REMOVED_ZERODHA_API_SECRET]')

c.execute('''INSERT INTO broker_credentials (id, user_id, broker_name, api_key, api_secret, is_active, created_at) 
             VALUES (?, ?, ?, ?, ?, ?, datetime("now"))''',
          (4, user_id, 'zerodha', encrypted_key, encrypted_secret, 1))

conn.commit()
print(f'[OK] Broker ID 4 created for user {user_id}')

# Verify
c.execute('SELECT id, user_id, broker_name FROM broker_credentials')
brokers = c.fetchall()
print('\nCurrent brokers:')
for b in brokers:
    print(f'  ID: {b[0]}, User: {b[1]}, Broker: {b[2]}')

conn.close()
