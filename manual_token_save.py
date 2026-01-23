"""
Manually exchange Zerodha request token and save to database
"""
import sqlite3
from kiteconnect import KiteConnect
import sys

# Your request token from the URL
request_token = "[REMOVED_REQUEST_TOKEN]"

# Get credentials from database
conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

c.execute('SELECT id, api_key, api_secret FROM broker_credentials WHERE id = 4')
broker = c.fetchone()

if not broker:
    print("❌ Broker not found!")
    sys.exit(1)

broker_id = broker[0]
encrypted_api_key = broker[1]
encrypted_api_secret = broker[2]

print(f"📋 Broker ID: {broker_id}")
print(f"🔐 Encrypted API Key: {encrypted_api_key[:30]}...")
print(f"🔐 Encrypted API Secret: {encrypted_api_secret[:30]}...")

# Decrypt credentials using backend's encryption manager
import sys
sys.path.insert(0, 'F:/ALGO/backend')
from app.core.security import encryption_manager

api_key = encryption_manager.decrypt_credentials(encrypted_api_key)
api_secret = encryption_manager.decrypt_credentials(encrypted_api_secret)

print(f"\n✅ Decrypted API Key: {api_key}")
print(f"✅ Decrypted API Secret: {api_secret[:10]}...")

# Initialize KiteConnect
print(f"\n🔄 Initializing KiteConnect with API key...")
kite = KiteConnect(api_key=api_key)

# Exchange request token for access token
print(f"🔄 Exchanging request token: {request_token}")
try:
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    
    print(f"\n✅ Access Token Received: {access_token}")
    print(f"📏 Token Length: {len(access_token)} chars")
    
    # Save to database
    print(f"\n💾 Saving access token to database...")
    c.execute('UPDATE broker_credentials SET access_token = ? WHERE id = ?', (access_token, broker_id))
    conn.commit()
    
    # Verify it was saved
    c.execute('SELECT access_token FROM broker_credentials WHERE id = 4')
    saved_token = c.fetchone()[0]
    
    if saved_token == access_token:
        print(f"✅ Token successfully saved to database!")
        print(f"🎉 Token: {saved_token[:30]}...")
        
        # Test the token by fetching margins
        print(f"\n🧪 Testing token by fetching margins...")
        kite.set_access_token(access_token)
        margins = kite.margins()
        
        print(f"\n✅ TOKEN WORKS! Account margins fetched successfully:")
        print(f"💰 Available Balance: ₹{margins['equity']['available']['live_balance']:.2f}")
        print(f"📊 Used Margin: ₹{margins['equity']['utilised']['debits']:.2f}")
        
    else:
        print(f"❌ Token save verification failed!")
        
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()
