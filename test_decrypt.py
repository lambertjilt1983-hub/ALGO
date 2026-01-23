import sys
sys.path.insert(0, 'f:/ALGO/backend')

from app.core.security import encryption_manager
import sqlite3

# Read the encrypted API key from DB
conn = sqlite3.connect('F:/ALGO/algotrade.db')
cursor = conn.cursor()
cursor.execute('SELECT api_key FROM broker_credentials WHERE id = 4')
encrypted_api_key = cursor.fetchone()[0]
conn.close()

print(f"Encrypted API Key from DB: {encrypted_api_key[:50]}...")

try:
    decrypted = encryption_manager.decrypt_credentials(encrypted_api_key)
    print(f"✓ Decrypted API Key: {decrypted}")
    print(f"✓ Length: {len(decrypted)}")
except Exception as e:
    print(f"✗ Decryption failed: {str(e)}")
