import sqlite3
import sys
sys.path.insert(0, 'F:/ALGO/backend')
from app.core.security import encryption_manager

# Fill these with your actual values
BROKER_ID = 4  # or any unique integer
USER_ID = 1  # update as needed
BROKER_NAME = 'zerodha'
API_KEY = '30i4qnng2thn7mfd'
API_SECRET = '0ol42oubvv9dpu8ruzw295or9vpthmxx'

# Encrypt credentials
encrypted_api_key = encryption_manager.encrypt_credentials(API_KEY)
encrypted_api_secret = encryption_manager.encrypt_credentials(API_SECRET)

conn = sqlite3.connect('F:/ALGO/algotrade.db')
c = conn.cursor()

c.execute('''INSERT INTO broker_credentials (id, user_id, broker_name, api_key, api_secret, is_active) VALUES (?, ?, ?, ?, ?, 1)''',
          (BROKER_ID, USER_ID, BROKER_NAME, encrypted_api_key, encrypted_api_secret))
conn.commit()
print(f"[SUCCESS] Inserted broker_credentials row for {BROKER_NAME} (id={BROKER_ID})")
conn.close()
