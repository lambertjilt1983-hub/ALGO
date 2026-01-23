import sys
sys.path.insert(0, 'F:/ALGO/backend')

from kiteconnect import KiteConnect
from app.core.security import encryption_manager
import sqlite3

# Get broker credentials
conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()
c.execute('SELECT id, api_key, api_secret FROM broker_credentials WHERE id = 4')
broker = c.fetchone()

broker_id = broker[0]
encrypted_api_key = broker[1]
encrypted_api_secret = broker[2]

print(f"Broker ID: {broker_id}")

# Decrypt credentials
try:
    api_key = encryption_manager.decrypt_credentials(encrypted_api_key)
    api_secret = encryption_manager.decrypt_credentials(encrypted_api_secret)
    print(f"API Key: {api_key[:10]}...")
    print(f"API Secret: {api_secret[:10]}...")
except Exception as e:
    print(f"Decryption error: {e}")
    conn.close()
    exit(1)

# Initialize KiteConnect
kite = KiteConnect(api_key=api_key)

# Exchange request token
request_token = "[REMOVED_REQUEST_TOKEN]"

try:
    print(f"\nExchanging request token: {request_token}")
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    print(f"✓ Access token received: {access_token[:30]}...")
    
    # Save to database
    c.execute('UPDATE broker_credentials SET access_token = ? WHERE id = ?', (access_token, broker_id))
    conn.commit()
    print(f"✓ Access token saved to database!")
    
    # Verify
    c.execute('SELECT access_token FROM broker_credentials WHERE id = 4')
    result = c.fetchone()
    print(f"✓ Verified in DB: {result[0][:30]}...")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

conn.close()
