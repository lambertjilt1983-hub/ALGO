#!/usr/bin/env python3
import sqlite3
from kiteconnect import KiteConnect
from app.core.security import encryption_manager
import sys

sys.path.insert(0, 'F:/ALGO/backend')

conn = sqlite3.connect('F:/ALGO/algotrade.db')
cursor = conn.cursor()
cursor.execute('SELECT api_key, access_token FROM broker_credentials WHERE id = 4')
result = cursor.fetchone()

if not result:
    print('❌ No broker found')
    sys.exit(1)

encrypted_api_key, access_token = result
print(f'Found broker with token: {access_token[:30]}...')

try:
    api_key = encryption_manager.decrypt_credentials(encrypted_api_key)
    print(f'✓ Decrypted API key: {api_key[:10]}...')
    
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    margins = kite.margins()
    print(f'✓ Token is VALID!')
    print(f'  Available Balance: {margins["equity"]["available"]["live_balance"]}')
    
except Exception as e:
    print(f'❌ Token is INVALID: {str(e)}')

conn.close()
